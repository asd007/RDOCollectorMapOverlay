"""
High-performance OpenGL collectible renderer using instanced drawing.

Uses modern OpenGL with:
- Texture atlas for all sprite types
- Vertex Buffer Objects (VBO) for sprite positions
- Instanced rendering (single draw call for all sprites)
- GPU-side viewport transforms

This achieves 60+ FPS with thousands of sprites.
"""

from PySide6.QtCore import Qt, Signal, Property, QSize, QRectF, QByteArray
from PySide6.QtQuick import QQuickFramebufferObject
from PySide6.QtGui import QOpenGLFramebufferObject, QOpenGLTexture, QImage, QPainter, QColor
from PySide6.QtOpenGL import QOpenGLShaderProgram, QOpenGLBuffer, QOpenGLVertexArrayObject, QOpenGLFunctions
from qml.svg_icons import get_icon_svg, get_icon_name
from PySide6.QtSvg import QSvgRenderer
import struct
import time
from typing import List, Dict


class CollectibleCanvasGL(QQuickFramebufferObject):
    """
    OpenGL-accelerated collectible renderer.

    Usage in QML:
        CollectibleCanvasGL {
            anchors.fill: parent
            collectibles: backend.visibleCollectibles
            viewportX: root.viewportX
            viewportY: root.viewportY
            viewportScale: root.scaleX
        }
    """

    # Signals
    collectiblesChanged = Signal()
    viewportXChanged = Signal()
    viewportYChanged = Signal()
    viewportScaleChanged = Signal()
    opacityValueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Enable transparency
        self.setMirrorVertically(True)  # Qt's FBO is flipped

        # Data
        self._collectibles: List[Dict] = []
        self._viewport_x: float = 0.0
        self._viewport_y: float = 0.0
        self._viewport_scale: float = 1.0
        self._opacity: float = 0.7

    def createRenderer(self):
        """Factory method called by Qt to create the OpenGL renderer"""
        return CollectibleRenderer(self)

    # Properties
    @Property('QVariantList', notify=collectiblesChanged)
    def collectibles(self):
        return self._collectibles

    @collectibles.setter
    def collectibles(self, value):
        self._collectibles = value
        self.collectiblesChanged.emit()
        self.update()

    @Property(float, notify=viewportXChanged)
    def viewportX(self):
        return self._viewport_x

    @viewportX.setter
    def viewportX(self, value):
        self._viewport_x = value
        self.viewportXChanged.emit()
        self.update()

    @Property(float, notify=viewportYChanged)
    def viewportY(self):
        return self._viewport_y

    @viewportY.setter
    def viewportY(self, value):
        self._viewport_y = value
        self.viewportYChanged.emit()
        self.update()

    @Property(float, notify=viewportScaleChanged)
    def viewportScale(self):
        return self._viewport_scale

    @viewportScale.setter
    def viewportScale(self, value):
        self._viewport_scale = value
        self.viewportScaleChanged.emit()
        self.update()

    @Property(float, notify=opacityValueChanged)
    def opacityValue(self):
        return self._opacity

    @opacityValue.setter
    def opacityValue(self, value):
        self._opacity = value
        self.opacityValueChanged.emit()
        self.update()


class CollectibleRenderer(QQuickFramebufferObject.Renderer):
    """
    OpenGL renderer implementation using instanced drawing.
    Runs on the render thread - all OpenGL calls happen here.
    """

    # Sprite types we need to render
    SPRITE_TYPES = [
        'arrowhead', 'bottle', 'coin', 'egg', 'flower',
        'tarot', 'jewelry', 'heirloom', 'fossil', 'random'
    ]

    # Vertex shader - transforms sprite quads with viewport matrix
    VERTEX_SHADER = """
    #version 330 core

    // Per-vertex attributes (quad vertices)
    layout(location = 0) in vec2 vertexPos;  // Quad corner: (0,0) to (1,1)
    layout(location = 1) in vec2 texCoord;   // Texture coords

    // Per-instance attributes (one per sprite)
    layout(location = 2) in vec2 spritePos;      // World position
    layout(location = 3) in float spriteType;    // Sprite type index
    layout(location = 4) in float spriteOpacity; // Individual opacity

    // Uniforms
    uniform vec2 viewportOffset;  // Camera offset
    uniform float viewportScale;  // Camera scale
    uniform vec2 screenSize;      // Framebuffer size
    uniform float spriteSize;     // Sprite size in pixels

    // Outputs to fragment shader
    out vec2 fragTexCoord;
    out float fragSpriteType;
    out float fragOpacity;

    void main() {
        // Transform sprite position through viewport
        vec2 worldPos = spritePos - viewportOffset;
        vec2 screenPos = worldPos * viewportScale;

        // Add vertex offset (scaled sprite quad)
        vec2 vertexOffset = (vertexPos - 0.5) * spriteSize;
        screenPos += vertexOffset;

        // Convert to clip space [-1, 1]
        vec2 clipPos = (screenPos / screenSize) * 2.0 - 1.0;
        clipPos.y = -clipPos.y;  // Flip Y

        gl_Position = vec4(clipPos, 0.0, 1.0);

        fragTexCoord = texCoord;
        fragSpriteType = spriteType;
        fragOpacity = spriteOpacity;
    }
    """

    # Fragment shader - samples texture atlas
    FRAGMENT_SHADER = """
    #version 330 core

    in vec2 fragTexCoord;
    in float fragSpriteType;
    in float fragOpacity;

    uniform sampler2D spriteAtlas;
    uniform float atlasRows;     // Number of sprite rows in atlas
    uniform float atlasCols;     // Number of sprite columns
    uniform float globalOpacity; // Global opacity multiplier

    out vec4 fragColor;

    void main() {
        // Calculate atlas coordinates for this sprite type
        float col = mod(fragSpriteType, atlasCols);
        float row = floor(fragSpriteType / atlasCols);

        // Scale texture coordinate to single sprite cell
        vec2 cellSize = vec2(1.0 / atlasCols, 1.0 / atlasRows);
        vec2 atlasCoord = vec2(col, row) * cellSize + fragTexCoord * cellSize;

        // Sample texture
        vec4 texColor = texture(spriteAtlas, atlasCoord);

        // Apply opacity
        texColor.a *= fragOpacity * globalOpacity;

        fragColor = texColor;
    }
    """

    def __init__(self, item: CollectibleCanvasGL):
        super().__init__()
        self.item = item

        # OpenGL objects (initialized in render thread)
        self.shader_program = None
        self.vao = None
        self.quad_vbo = None
        self.instance_vbo = None
        self.texture = None
        self.initialized = False

        # Rendering state
        self.sprite_count = 0

        # FPS tracking
        self.frame_times = []
        self.last_fps_log = time.time()

    def createFramebufferObject(self, size: QSize):
        """Create FBO with transparency"""
        format = QOpenGLFramebufferObject.Attachment.CombinedDepthStencil
        return QOpenGLFramebufferObject(size, format)

    def render(self):
        """Main render function - called by Qt on render thread"""
        if not self.initialized:
            self.initialize_gl()
            self.initialized = True

        if not self.shader_program:
            return

        # Track FPS
        now = time.time()
        self.frame_times.append(now)
        if now - self.last_fps_log >= 1.0:
            cutoff = now - 1.0
            self.frame_times = [t for t in self.frame_times if t > cutoff]
            fps = len(self.frame_times)
            print(f"[GL Renderer] FPS: {fps}")
            self.last_fps_log = now

        # Get OpenGL functions
        if not hasattr(self, 'gl'):
            self.gl = QOpenGLFunctions()
            self.gl.initializeOpenGLFunctions()

        # Clear with transparent black
        self.gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_DEPTH_BUFFER_BIT)

        # Enable blending for transparency
        self.gl.glEnable(self.gl.GL_BLEND)
        self.gl.glBlendFunc(self.gl.GL_SRC_ALPHA, self.gl.GL_ONE_MINUS_SRC_ALPHA)

        # Update instance data and render
        self.update_instances()
        self.draw_instances()

    def initialize_gl(self):
        """Initialize OpenGL resources (shaders, buffers, textures)"""
        print("[GL Renderer] Initializing OpenGL resources...")

        # Create shader program
        self.shader_program = QOpenGLShaderProgram()
        if not self.shader_program.addShaderFromSourceCode(
            QOpenGLShaderProgram.ShaderTypeBit.Vertex, self.VERTEX_SHADER
        ):
            print(f"[GL Renderer] Vertex shader error: {self.shader_program.log()}")
            return

        if not self.shader_program.addShaderFromSourceCode(
            QOpenGLShaderProgram.ShaderTypeBit.Fragment, self.FRAGMENT_SHADER
        ):
            print(f"[GL Renderer] Fragment shader error: {self.shader_program.log()}")
            return

        if not self.shader_program.link():
            print(f"[GL Renderer] Shader link error: {self.shader_program.log()}")
            return

        print("[GL Renderer] Shaders compiled successfully")

        # Create VAO
        self.vao = QOpenGLVertexArrayObject()
        self.vao.create()
        self.vao.bind()

        # Create quad VBO (shared vertices for all sprites)
        self.setup_quad_geometry()

        # Create instance VBO (per-sprite data)
        self.instance_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.instance_vbo.create()
        self.instance_vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.DynamicDraw)

        # Create texture atlas
        self.create_texture_atlas()

        self.vao.release()

        print("[GL Renderer] OpenGL initialization complete")

    def setup_quad_geometry(self):
        """Create quad geometry (2 triangles) for sprite rendering"""
        # Quad vertices: position (x, y) + texcoord (u, v)
        quad_data = [
            # Triangle 1
            0.0, 0.0,  0.0, 0.0,  # Bottom-left
            1.0, 0.0,  1.0, 0.0,  # Bottom-right
            1.0, 1.0,  1.0, 1.0,  # Top-right
            # Triangle 2
            0.0, 0.0,  0.0, 0.0,  # Bottom-left
            1.0, 1.0,  1.0, 1.0,  # Top-right
            0.0, 1.0,  0.0, 1.0,  # Top-left
        ]

        # Pack as bytes
        quad_bytes = struct.pack(f'{len(quad_data)}f', *quad_data)

        self.quad_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.quad_vbo.create()
        self.quad_vbo.bind()
        self.quad_vbo.allocate(quad_bytes, len(quad_bytes))

        # Setup vertex attributes
        stride = 4 * 4  # 4 floats * 4 bytes
        GL_FLOAT = 0x1406  # OpenGL constant

        # Attribute 0: vertexPos (vec2)
        self.shader_program.enableAttributeArray(0)
        self.shader_program.setAttributeBuffer(0, GL_FLOAT, 0, 2, stride)

        # Attribute 1: texCoord (vec2)
        self.shader_program.enableAttributeArray(1)
        self.shader_program.setAttributeBuffer(1, GL_FLOAT, 8, 2, stride)

        self.quad_vbo.release()

    def create_texture_atlas(self):
        """Create texture atlas with all sprite types"""
        print("[GL Renderer] Creating texture atlas...")

        sprite_size = 48
        cols = 4  # 4 sprites per row
        rows = (len(self.SPRITE_TYPES) + cols - 1) // cols

        atlas_width = sprite_size * cols
        atlas_height = sprite_size * rows

        # Create atlas image
        atlas_image = QImage(atlas_width, atlas_height, QImage.Format.Format_ARGB32)
        atlas_image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(atlas_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Render each sprite type into atlas
        for i, sprite_type in enumerate(self.SPRITE_TYPES):
            col = i % cols
            row = i // cols
            x = col * sprite_size
            y = row * sprite_size

            # Render SVG
            svg_data = get_icon_svg(sprite_type)
            svg_renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
            if svg_renderer.isValid():
                painter.save()
                painter.translate(x, y)
                svg_renderer.render(painter, QRectF(0, 0, sprite_size, sprite_size))
                painter.restore()

        painter.end()

        # Upload to GPU
        self.texture = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
        self.texture.setData(atlas_image)
        self.texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
        self.texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
        self.texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)

        print(f"[GL Renderer] Texture atlas created: {atlas_width}x{atlas_height}, {len(self.SPRITE_TYPES)} sprites")

    def update_instances(self):
        """Update instance buffer with current collectible positions"""
        collectibles = self.item._collectibles

        if not collectibles:
            self.sprite_count = 0
            return

        # Build instance data: position (x, y), type, opacity
        instance_data = []
        for col in collectibles:
            x = col.get('map_x', 0)
            y = col.get('map_y', 0)
            col_type = col.get('type', 'random')
            is_collected = col.get('collected', False)

            # Map type to atlas index
            icon_name = get_icon_name(col_type)
            try:
                type_index = float(self.SPRITE_TYPES.index(icon_name))
            except ValueError:
                type_index = float(self.SPRITE_TYPES.index('random'))

            opacity = 0.5 if is_collected else 1.0

            instance_data.extend([x, y, type_index, opacity])

        # Upload to GPU
        if instance_data:
            instance_bytes = struct.pack(f'{len(instance_data)}f', *instance_data)

            self.vao.bind()
            self.instance_vbo.bind()
            self.instance_vbo.allocate(instance_bytes, len(instance_bytes))

            # Setup instance attributes (divisor = 1 means per-instance)
            stride = 4 * 4  # 4 floats * 4 bytes
            GL_FLOAT = 0x1406

            # Attribute 2: spritePos (vec2)
            self.shader_program.enableAttributeArray(2)
            self.shader_program.setAttributeBuffer(2, GL_FLOAT, 0, 2, stride)
            self.gl.glVertexAttribDivisor(2, 1)

            # Attribute 3: spriteType (float)
            self.shader_program.enableAttributeArray(3)
            self.shader_program.setAttributeBuffer(3, GL_FLOAT, 8, 1, stride)
            self.gl.glVertexAttribDivisor(3, 1)

            # Attribute 4: spriteOpacity (float)
            self.shader_program.enableAttributeArray(4)
            self.shader_program.setAttributeBuffer(4, GL_FLOAT, 12, 1, stride)
            self.gl.glVertexAttribDivisor(4, 1)

            self.instance_vbo.release()
            self.vao.release()

            self.sprite_count = len(collectibles)

    def draw_instances(self):
        """Draw all sprites with a single instanced draw call"""
        if self.sprite_count == 0:
            return

        self.shader_program.bind()
        self.vao.bind()

        # Bind texture
        if self.texture:
            self.texture.bind()

        # Set uniforms
        self.shader_program.setUniformValue("viewportOffset",
            self.item._viewport_x, self.item._viewport_y)
        self.shader_program.setUniformValue("viewportScale", self.item._viewport_scale)
        self.shader_program.setUniformValue("screenSize",
            float(self.framebufferObject().width()),
            float(self.framebufferObject().height()))
        self.shader_program.setUniformValue("spriteSize", 48.0)
        self.shader_program.setUniformValue("globalOpacity", self.item._opacity)
        self.shader_program.setUniformValue("spriteAtlas", 0)
        self.shader_program.setUniformValue("atlasRows", 3.0)  # Adjust based on SPRITE_TYPES
        self.shader_program.setUniformValue("atlasCols", 4.0)

        # Instanced draw call - renders all sprites at once!
        GL_TRIANGLES = 0x0004
        self.gl.glDrawArraysInstanced(GL_TRIANGLES, 0, 6, self.sprite_count)

        self.vao.release()
        self.shader_program.release()

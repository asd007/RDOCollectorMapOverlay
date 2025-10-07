import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtWebEngineQuick 1.0
import theme 1.0

/*
 * Video Player Window
 *
 * Embedded YouTube player that appears on top of the game screen.
 * Replicates Electron video player behavior:
 * - Centered viewport (900x600)
 * - Click-through disabled when open
 * - Semi-transparent backdrop overlay
 * - Close button re-enables click-through
 */

Window {
    id: videoWindow

    // Window properties
    width: 900
    height: 600
    visible: false
    color: "transparent"

    // Centered on screen
    x: (Screen.width - width) / 2
    y: (Screen.height - height) / 2

    // Frameless, always-on-top
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    // Video metadata
    property string videoUrl: ""
    property string collectibleName: ""
    property string videoId: ""
    property int startSeconds: 0

    // Background overlay (semi-transparent black)
    Rectangle {
        anchors.fill: parent
        color: "#d9000000"  // rgba(0, 0, 0, 0.85)
        z: -1

        // Extend beyond window bounds to create full-screen overlay effect
        // (This mimics the Electron box-shadow trick)
        anchors.margins: -5000
    }

    // Main player container
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        border.color: Theme.accentYellow
        border.width: 3
        radius: 12

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 20

            // Header with title and close button
            RowLayout {
                Layout.fillWidth: true
                spacing: 0

                Text {
                    text: collectibleName + " - Video Guide"
                    color: Theme.accentYellow
                    font.pixelSize: 24
                    font.weight: Font.Bold
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                }

                Button {
                    text: "X Close"
                    background: Rectangle {
                        color: closeButton.hovered ? "#dc2626" : "#ef4444"
                        radius: 8

                        Behavior on color {
                            ColorAnimation { duration: 150 }
                        }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "white"
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    padding: 12
                    implicitWidth: 120

                    property bool hovered: false

                    MouseArea {
                        id: closeButton
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        onEntered: parent.hovered = true
                        onExited: parent.hovered = false

                        onClicked: {
                            console.log("[VideoPlayer] Close button clicked")
                            closeVideoPlayer()
                        }
                    }
                }
            }

            // YouTube player iframe
            Rectangle {
                id: webViewContainer
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#1a1a1a"
                radius: 8

                Text {
                    anchors.centerIn: parent
                    text: "Loading video player..."
                    color: Theme.textSecondary
                    font.pixelSize: 18
                    font.family: Theme.fontFamily
                    visible: !webViewLoader.item
                }

                Loader {
                    id: webViewLoader
                    anchors.fill: parent
                    active: false

                    sourceComponent: Component {
                        WebEngineView {
                            id: webView

                            // YouTube embed URL
                            url: {
                                if (videoId) {
                                    var embedUrl = "https://www.youtube.com/embed/" + videoId
                                    embedUrl += "?autoplay=1&rel=0&modestbranding=1"
                                    if (startSeconds > 0) {
                                        embedUrl += "&start=" + startSeconds
                                    }
                                    return embedUrl
                                }
                                return ""
                            }

                            onLoadingChanged: function(loadRequest) {
                                if (loadRequest.errorString) {
                                    console.log("[VideoPlayer] Load error:", loadRequest.errorString)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Show video player with URL parsing
    function show(url, name) {
        console.log("[VideoPlayer] Opening video:", name)
        console.log("[VideoPlayer] URL:", url)

        videoUrl = url
        collectibleName = name

        // Extract YouTube video ID
        var youtubeMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&?]+)/)
        if (!youtubeMatch) {
            console.error("[VideoPlayer] Invalid YouTube URL:", url)
            return
        }

        videoId = youtubeMatch[1]

        // Parse timestamp
        startSeconds = 0

        // Check for t= parameter (t=120s, t=2m30s, etc.)
        var timeMatch = url.match(/[?&]t=(\d+)([hms]?)/)
        if (timeMatch) {
            var value = parseInt(timeMatch[1])
            var unit = timeMatch[2] || 's'

            if (unit === 'h') {
                startSeconds = value * 3600
            } else if (unit === 'm') {
                startSeconds = value * 60
            } else {
                startSeconds = value
            }
        }

        // Check for #t= format
        var hashTimeMatch = url.match(/#t=(\d+)/)
        if (hashTimeMatch) {
            startSeconds = parseInt(hashTimeMatch[1])
        }

        if (startSeconds > 0) {
            var minutes = Math.floor(startSeconds / 60)
            var seconds = startSeconds % 60
            console.log("[VideoPlayer] Starting at " + minutes + ":" + (seconds < 10 ? "0" : "") + seconds + " (" + startSeconds + "s)")
        }

        // Activate webview loader
        webViewLoader.active = true

        // Show window
        videoWindow.visible = true

        // Disable click-through in main overlay
        backend.disable_click_through()
    }

    // Close video player
    function closeVideoPlayer() {
        console.log("[VideoPlayer] Closing video player")
        videoWindow.visible = false

        // Deactivate webview to stop video
        webViewLoader.active = false

        // Clear video
        videoId = ""
        startSeconds = 0

        // Re-enable click-through in main overlay
        backend.enable_click_through()
    }

    // ESC key to close
    Shortcut {
        sequence: "Esc"
        onActivated: closeVideoPlayer()
    }
}

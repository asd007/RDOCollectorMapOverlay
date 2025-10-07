// Theme.qml - Centralized design system (Qt Singleton)
pragma Singleton
import QtQuick 2.15

QtObject {
    id: theme

    // =================================================================
    // COLORS (Matching Electron Design)
    // =================================================================

    // Panel Backgrounds
    readonly property color panelDark: "#F2000000"        // rgba(0, 0, 0, 0.95)
    readonly property color panelMedium: "#F2282828"      // rgba(40, 40, 40, 0.95)
    readonly property color panelLight: "#CC323232"       // rgba(50, 50, 50, 0.8)
    readonly property color widgetBackground: "#C8000000" // rgba(0, 0, 0, 0.8)

    // Accent Colors
    readonly property color accentYellow: "#fcd34d"       // Primary accent
    readonly property color accentOrange: "#fbbf24"       // Secondary accent
    readonly property color accentOrangeDark: "#D97706"   // Borders

    // Status Colors
    readonly property color success: "#22c55e"            // Green (tracking)
    readonly property color error: "#ef4444"              // Red (errors)
    readonly property color warning: "#eab308"            // Amber (warnings)

    // Text Colors
    readonly property color textPrimary: "#f3f4f6"        // White text
    readonly property color textSecondary: "#d1d5db"      // Light gray
    readonly property color textTertiary: "#9ca3af"       // Medium gray
    readonly property color textDisabled: "#6b7280"       // Dark gray
    readonly property color textComplete: "#34d399"       // Green (completed items)

    // Border Colors
    readonly property color borderPrimary: "#888888"
    readonly property color borderAccent: "#B3fbbf24"     // Orange border (tracker)
    readonly property color borderWidget: "#80D97706"     // Semi-transparent orange
    readonly property color borderSubtle: "#80647487"     // Gray border

    // Interactive States
    readonly property color hoverBackground: "#4D000000"  // Hover overlay
    readonly property color activeBackground: "#66D97706" // Active tab
    readonly property color pressedBackground: "#33D97706" // Pressed state

    // =================================================================
    // TYPOGRAPHY
    // =================================================================

    // Font Families
    readonly property string fontFamily: "Segoe UI"
    readonly property string fontFamilyMono: "Consolas"
    readonly property string fontFamilyEmoji: "Segoe UI Emoji"

    // Font Sizes
    readonly property int fontHuge: 32
    readonly property int fontLarge: 24
    readonly property int fontMedium: 20
    readonly property int fontBody: 16
    readonly property int fontSmall: 14
    readonly property int fontTiny: 12
    readonly property int fontMicro: 10

    // Font Weights (use with font.weight)
    readonly property int fontWeightLight: Font.Light
    readonly property int fontWeightNormal: Font.Normal
    readonly property int fontWeightMedium: Font.DemiBold
    readonly property int fontWeightBold: Font.Bold

    // =================================================================
    // DIMENSIONS
    // =================================================================

    // Tracker Dimensions
    readonly property int trackerWidth: 420
    readonly property int trackerHeaderHeight: 68
    readonly property int trackerTabHeight: 48
    readonly property int trackerFooterHeight: 60

    // Widget Dimensions
    readonly property int statusPillWidth: 140
    readonly property int statusPillHeight: 40
    readonly property int fpsCounterWidth: 100
    readonly property int fpsCounterHeight: 40

    // Item Heights
    readonly property int setHeaderHeight: 44
    readonly property int setItemHeight: 36

    // Border Widths
    readonly property int borderThin: 1
    readonly property int borderMedium: 2
    readonly property int borderThick: 3

    // Border Radius
    readonly property int radiusSmall: 4
    readonly property int radiusMedium: 8
    readonly property int radiusLarge: 12

    // =================================================================
    // SPACING
    // =================================================================

    // Margins
    readonly property int marginHuge: 30
    readonly property int marginLarge: 20
    readonly property int marginMedium: 15
    readonly property int marginSmall: 12
    readonly property int marginTiny: 8
    readonly property int marginMicro: 4

    // Padding (inside containers)
    readonly property int paddingLarge: 15
    readonly property int paddingMedium: 12
    readonly property int paddingSmall: 8
    readonly property int paddingTiny: 6
    readonly property int paddingMicro: 4

    // Spacing (between items)
    readonly property int spacingLarge: 20
    readonly property int spacingMedium: 12
    readonly property int spacingSmall: 8
    readonly property int spacingTiny: 4
    readonly property int spacingMicro: 2

    // =================================================================
    // ANIMATION
    // =================================================================

    // Durations
    readonly property int animationFast: 150
    readonly property int animationNormal: 300
    readonly property int animationSlow: 500

    // Easing Curves
    readonly property int easingStandard: Easing.InOutQuad
    readonly property int easingEnter: Easing.OutCubic
    readonly property int easingExit: Easing.InCubic

    // =================================================================
    // Z-INDEX (Layer Ordering)
    // =================================================================

    readonly property int zBackground: 0
    readonly property int zContent: 100
    readonly property int zOverlay: 200
    readonly property int zModal: 300
    readonly property int zTooltip: 400

    // =================================================================
    // OPACITY
    // =================================================================

    readonly property real opacityFull: 1.0
    readonly property real opacityHigh: 0.9
    readonly property real opacityMedium: 0.7
    readonly property real opacityLow: 0.5
    readonly property real opacityDisabled: 0.3

    // =================================================================
    // SCROLLBAR
    // =================================================================

    readonly property int scrollbarWidth: 9
    readonly property int scrollbarRadius: 4
    readonly property color scrollbarThumb: borderAccent
    readonly property color scrollbarTrack: "#4D000000"
}

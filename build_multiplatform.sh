#!/bin/bash
# Script to build multi-platform Docker images including Windows support
# This script builds separate Linux and Windows images and combines them into a manifest

# Default values
IMAGE_NAME="mcp-instana"
IMAGE_TAG="latest"
REGISTRY=""
LINUX_PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7,linux/386,linux/ppc64le,linux/s390x"
WINDOWS_PLATFORMS="windows/amd64"
BUILD_LINUX=true
BUILD_WINDOWS=true
PUSH=false

# Display help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Build a multi-platform Docker image including Windows support"
    echo ""
    echo "Options:"
    echo "  -n, --name NAME       Image name (default: mcp-instana)"
    echo "  -t, --tag TAG         Image tag (default: latest)"
    echo "  -r, --registry REG    Registry prefix (e.g., 'username/' or 'registry.example.com/')"
    echo "  --linux-only          Build only Linux images (default: build both)"
    echo "  --windows-only        Build only Windows images (default: build both)"
    echo "  --push                Push the images to the registry"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --name mcp-instana --tag v1.0 --registry username/ --push"
    echo "  $0 --linux-only --registry username/ --push"
    echo "  $0 --windows-only --registry username/ --push"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        --linux-only)
            BUILD_LINUX=true
            BUILD_WINDOWS=false
            shift
            ;;
        --windows-only)
            BUILD_LINUX=false
            BUILD_WINDOWS=true
            shift
            ;;
        --push)
            PUSH=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Full image names with registry and tag
FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
LINUX_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}-linux"
WINDOWS_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}-windows"

# Set up Docker BuildKit builder
echo "Setting up Docker BuildKit builder..."
docker buildx create --name multiplatform --driver docker-container --use 2>/dev/null || true

# Build Linux images if requested
if [ "$BUILD_LINUX" = true ]; then
    echo "Building Linux images: $LINUX_IMAGE_NAME"
    echo "Platforms: $LINUX_PLATFORMS"
    
    # Build command for Linux
    BUILD_CMD="docker buildx build --platform $LINUX_PLATFORMS -t $LINUX_IMAGE_NAME -f Dockerfile"
    
    # Add push flag if requested
    if [ "$PUSH" = true ]; then
        BUILD_CMD="$BUILD_CMD --push"
        echo "Linux images will be pushed to registry"
    else
        echo "WARNING: Cannot load multi-platform images locally. Use --push flag to create multi-platform images."
        echo "Building only for the current platform..."
        # Get current platform
        CURRENT_PLATFORM=$(docker version -f '{{.Server.Os}}/{{.Server.Arch}}' | tr '[:upper:]' '[:lower:]')
        if [[ $CURRENT_PLATFORM == linux/* ]]; then
            BUILD_CMD="docker buildx build --platform $CURRENT_PLATFORM -t $LINUX_IMAGE_NAME -f Dockerfile --load"
        else
            echo "Current platform is not Linux. Skipping local build."
            BUILD_CMD=""
        fi
    fi
    
    # Add context
    if [ ! -z "$BUILD_CMD" ]; then
        BUILD_CMD="$BUILD_CMD ."
        
        # Execute build
        echo "Executing: $BUILD_CMD"
        eval $BUILD_CMD
        
        if [ $? -ne 0 ]; then
            echo "Linux build failed!"
            exit 1
        fi
    fi
fi

# Build Windows images if requested
if [ "$BUILD_WINDOWS" = true ]; then
    echo "Building Windows images: $WINDOWS_IMAGE_NAME"
    echo "Platforms: $WINDOWS_PLATFORMS"
    
    # Build command for Windows
    BUILD_CMD="docker buildx build --platform $WINDOWS_PLATFORMS -t $WINDOWS_IMAGE_NAME -f Dockerfile.windows"
    
    # Add push flag if requested
    if [ "$PUSH" = true ]; then
        BUILD_CMD="$BUILD_CMD --push"
        echo "Windows images will be pushed to registry"
    else
        echo "WARNING: Cannot load Windows images locally on non-Windows hosts. Use --push flag."
        # Check if running on Windows
        if [[ $(uname) == *"MINGW"* || $(uname) == *"MSYS"* ]]; then
            BUILD_CMD="docker buildx build --platform $WINDOWS_PLATFORMS -t $WINDOWS_IMAGE_NAME -f Dockerfile.windows --load"
        else
            echo "Current host is not Windows. Skipping local build."
            BUILD_CMD=""
        fi
    fi
    
    # Add context
    if [ ! -z "$BUILD_CMD" ]; then
        BUILD_CMD="$BUILD_CMD ."
        
        # Execute build
        echo "Executing: $BUILD_CMD"
        eval $BUILD_CMD
        
        if [ $? -ne 0 ]; then
            echo "Windows build failed!"
            exit 1
        fi
    fi
fi

# Create and push manifest if both Linux and Windows were built and pushed
if [ "$PUSH" = true ] && [ "$BUILD_LINUX" = true ] && [ "$BUILD_WINDOWS" = true ]; then
    echo "Creating manifest list: $FULL_IMAGE_NAME"
    
    # Create manifest
    docker manifest create $FULL_IMAGE_NAME $LINUX_IMAGE_NAME $WINDOWS_IMAGE_NAME
    
    # Push manifest
    docker manifest push $FULL_IMAGE_NAME
    
    echo "Manifest pushed as: $FULL_IMAGE_NAME"
    echo "This image will now work on both Linux and Windows hosts!"
elif [ "$PUSH" = true ]; then
    if [ "$BUILD_LINUX" = true ]; then
        echo "Only Linux images were built and pushed as: $LINUX_IMAGE_NAME"
    fi
    if [ "$BUILD_WINDOWS" = true ]; then
        echo "Only Windows images were built and pushed as: $WINDOWS_IMAGE_NAME"
    fi
else
    echo "Images were built locally but not pushed. Use --push to create multi-platform images."
fi

echo "Build process completed!"

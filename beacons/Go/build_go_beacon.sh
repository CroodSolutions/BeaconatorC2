#!/bin/bash

echo "Building Go Beacon..."

cd "$(dirname "$0")"

echo "Building for current platform..."
go build -ldflags="-s -w" -o go_beacon go_beacon.go

echo "Building for Windows (64-bit)..."
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o go_beacon_windows.exe go_beacon.go

echo "Building for Linux (64-bit)..."
GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o go_beacon_linux go_beacon.go

echo "Building for macOS (64-bit)..."
GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o go_beacon_macos go_beacon.go

echo "Build complete!"
echo "Binaries created:"
ls -la go_beacon*
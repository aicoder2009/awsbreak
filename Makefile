.PHONY: build clean test install run

# Binary name
BINARY=awsbreak
VERSION=1.0.0

# Build directory
BUILD_DIR=bin

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOCLEAN=$(GOCMD) clean
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod

# Build the binary
build:
	@mkdir -p $(BUILD_DIR)
	$(GOBUILD) -o $(BUILD_DIR)/$(BINARY) -ldflags "-X main.version=$(VERSION)" ./cmd/aws-hit-breaks/

# Clean build artifacts
clean:
	$(GOCLEAN)
	rm -rf $(BUILD_DIR)
	rm -rf tmp .gocache

# Run tests
test:
	$(GOTEST) -v ./...

# Install dependencies
deps:
	$(GOMOD) download
	$(GOMOD) tidy

# Install the binary to GOPATH/bin
install: build
	cp $(BUILD_DIR)/$(BINARY) $(GOPATH)/bin/

# Run the CLI
run: build
	./$(BUILD_DIR)/$(BINARY)

# Build for all platforms
build-all:
	@mkdir -p $(BUILD_DIR)
	GOOS=darwin GOARCH=amd64 $(GOBUILD) -o $(BUILD_DIR)/$(BINARY)-darwin-amd64 ./cmd/aws-hit-breaks/
	GOOS=darwin GOARCH=arm64 $(GOBUILD) -o $(BUILD_DIR)/$(BINARY)-darwin-arm64 ./cmd/aws-hit-breaks/
	GOOS=linux GOARCH=amd64 $(GOBUILD) -o $(BUILD_DIR)/$(BINARY)-linux-amd64 ./cmd/aws-hit-breaks/
	GOOS=linux GOARCH=arm64 $(GOBUILD) -o $(BUILD_DIR)/$(BINARY)-linux-arm64 ./cmd/aws-hit-breaks/
	GOOS=windows GOARCH=amd64 $(GOBUILD) -o $(BUILD_DIR)/$(BINARY)-windows-amd64.exe ./cmd/aws-hit-breaks/

# Help
help:
	@echo "Available targets:"
	@echo "  build      - Build the binary"
	@echo "  clean      - Clean build artifacts"
	@echo "  test       - Run tests"
	@echo "  deps       - Download dependencies"
	@echo "  install    - Install to GOPATH/bin"
	@echo "  run        - Build and run"
	@echo "  build-all  - Build for all platforms"

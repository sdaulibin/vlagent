RELEASE_REGISTRY?=harbor.devops.qdb.com/vl-flow
RELEASE_VERSION?=$(shell git rev-parse --short HEAD)
RELEASE_IMAGE:=$(RELEASE_REGISTRY)/vlagent-front:$(RELEASE_VERSION)

.PHONY: all
all: install build

.PHONY: install
install:
	npm install

.PHONY: build
build:
	npm run build:docker

.PHONY: clean
clean:
	rm -rf ./dist
	rm -rf ./node_modules

.PHONY: release-image.amd64
release-image.amd64: clean
	nerdctl build --build-arg NPM_REGISTRY="$(NPM_REGISTRY)" -t $(RELEASE_IMAGE)-amd64 .

.PHONY: release-image.arm64
release-image.arm64: clean
	nerdctl build --build-arg NPM_REGISTRY="$(NPM_REGISTRY)" -t $(RELEASE_IMAGE)-arm64 .

# Copyright 2020 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

RELEASE_REGISTRY?=harbor.devops.qdb.com/star
RELEASE_VERSION?=$(shell git rev-parse --short HEAD)
RELEASE_IMAGE:=$(RELEASE_REGISTRY)/vlagent-frontend:$(RELEASE_VERSION)

.PHONY: all
all: install build

.PHONY: install
install:
	npm install

.PHONY: install-deps
install-deps:
	npm install

.PHONY: build
build: build-app

# 修改目标名称，确保与Dockerfile中使用的名称一致
.PHONY: build-app
build-app: install-deps
	RELEASE_VERSION=$(RELEASE_VERSION) ENV_CONFIG=$(ENV_CONFIG) npm run $(ENV_CONFIG)

# 保留原来的目标名称作为别名，以便向后兼容
.PHONY: build-vlagent-frontend
build-vlagent-frontend: build-app

.PHONY: clean
clean:
	rm -rf ./dist
	rm -rf ./node_modules

.PHONY: release-image.amd64
release-image.amd64: clean
	nerdctl build --build-arg RELEASE_VERSION="$(RELEASE_VERSION)" --build-arg RELEASE_REGISTRY="$(RELEASE_REGISTRY)" --build-arg RELEASE_IMAGE="$(RELEASE_IMAGE)" --build-arg NPM_REGISTRY="$(NPM_REGISTRY)"  --build-arg ENV_CONFIG="$(ENV_CONFIG)" -t $(RELEASE_IMAGE)-amd64 .

.PHONY: release-image.arm64
release-image.arm64: clean 
	nerdctl build --build-arg RELEASE_VERSION="$(RELEASE_VERSION)" --build-arg RELEASE_REGISTRY="$(RELEASE_REGISTRY)" --build-arg RELEASE_IMAGE="$(RELEASE_IMAGE)" --build-arg NPM_REGISTRY="$(NPM_REGISTRY)" --build-arg ENV_CONFIG="$(ENV_CONFIG)" -t $(RELEASE_IMAGE)-arm64 .

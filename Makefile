XU ?= xu
PYTHON ?= python3
export XU

.PHONY: native check test demo smoke gpu-smoke
native:
	$(PYTHON) native/build.py --xu "$(XU)"

check: native
	$(XU) check examples/arena/main.xu
	$(XU) check examples/headless/main.xu

test: native
	mkdir -p build
	$(XU) build tests/core_checks.xu -o build/core-tests
	./build/core-tests

demo: native
	mkdir -p build
	$(XU) build examples/arena/main.xu -o build/arena
	./build/arena

smoke: native
	mkdir -p build
	$(XU) build examples/headless/main.xu -o build/headless
	./build/headless
	$(XU) build examples/arena/main.xu -o build/arena
	./build/arena --frames 120 --autoplay --capture build/arena.png

gpu-smoke: native
	mkdir -p build
	$(XU) build tests/gpu_smoke.xu -o build/gpu-smoke
	./build/gpu-smoke

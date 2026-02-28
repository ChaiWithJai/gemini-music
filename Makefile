.PHONY: day0 day0_quick ci run release

day0:
	./scripts/day0.sh

day0_quick:
	./scripts/day0.sh --quick

ci:
	cd api && make ci

run:
	cd api && make run

release:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make release VERSION=vX.Y.Z"; \
		exit 1; \
	fi
	./scripts/release.sh $(VERSION)

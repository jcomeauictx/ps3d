SOURCES = $(wildcard *.py)
LINT = $(SOURCES:.py=.lint)
TEST = $(SOURCES:.py=.doctest)
PYTHON ?= python3
PYLINT ?= pylint3  # may be simply `pylint`, especially on Debian 11+
GSTIME ?= 3  # timeout for postscript view
MLTIME ?= 10  # timeout for meshlab (obj viewer) needs longer loading time
# set timeouts to 0 for no timeout
export

all: lint test run
run: test.view
lint: $(LINT)
test: $(TEST)
%.lint: %.py
	$(PYLINT) $<
%.doctest: %.py
	$(PYTHON) -m doctest $<
%.mtl %.obj: ps3d.py %.ps3d
	./$+ $(@:.mtl=.obj) $(@:.obj=.mtl)
%.view: %.obj
	-cd $(<D) && timeout $(MLTIME) meshlab $(<F)
view: sample/a_test.view
%.ps: %.ps3d
	-timeout $(GSTIME) gs $<
%.ps: .FORCE
	-timeout $(GSTIME) gs $@
ps: test.ps
clean:
	rm -f *.obj *.mtl
.PRECIOUS: %.obj %.mtl
.FORCE:

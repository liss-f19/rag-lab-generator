override CFLAGS=-Wall -Wextra -fanalyzer -g -O0 -fsanitize=address,undefined

ifdef CI
override CFLAGS=-Wall -Wextra -Werror
endif

.PHONY: clean all

all: sop-mss

sop-mss: sop-mss.c
	gcc $(CFLAGS) -o sop-mss sop-mss.c

clean:
	rm -f sop-mss

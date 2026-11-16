override CFLAGS=-Wall -Wextra -fanalyzer -g -O0 -fsanitize=address,undefined

ifdef CI
override CFLAGS=-Wall -Wextra -Werror
endif

.PHONY: clean all

all: sop-pool

sop-pool: sop-pool.c
	gcc $(CFLAGS) -o sop-pool sop-pool.c

clean:
	rm -f sop-pool

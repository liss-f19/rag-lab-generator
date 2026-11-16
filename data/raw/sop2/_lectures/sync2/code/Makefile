CC = gcc
CFLAGS = -Wall -Wextra
LDFLAGS = -lrt

TARGETS = sem_shm aggregator sensor bounded_buffer_sem record_db_setup record_db_worker record_db_setup_global record_db_worker_global mtx_attributes record_db_setup_robust record_db_worker_robust bounded_buffer_cv readers_writers_cv

.PHONY: all clean

all: $(TARGETS)

%: %.c
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

record_db_setup record_db_worker: record_db.h

record_db_setup_global: record_db_setup.c record_db.h
	$(CC) $(CFLAGS) -DRECORD_DB_GLOBAL_LOCK $< -o $@ $(LDFLAGS)

record_db_worker_global: record_db_worker.c record_db.h
	$(CC) $(CFLAGS) -DRECORD_DB_GLOBAL_LOCK $< -o $@ $(LDFLAGS)

record_db_setup_robust: record_db_setup.c record_db.h
	$(CC) $(CFLAGS) -DRECORD_DB_ROBUST $< -o $@ $(LDFLAGS)

record_db_worker_robust: record_db_worker_robust.c record_db.h
	$(CC) $(CFLAGS) -DRECORD_DB_ROBUST $< -o $@ $(LDFLAGS)

clean:
	rm -f $(TARGETS) *.o
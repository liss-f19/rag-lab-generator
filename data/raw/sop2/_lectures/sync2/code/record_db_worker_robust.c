#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <pthread.h>
#include <errno.h>

#include "record_db.h"

long long recursive_chain_hash(long long current_val, int steps_left) {
    if (steps_left <= 0) {
        return current_val;
    }

    char data_chunk[512];
    snprintf(data_chunk, sizeof(data_chunk), "RECORD_STATE:[%lld]-STEP:[%d]-SALT:[x8f9q]",
             current_val, steps_left);

    // Dan Bernstein's djb2 hashing algorithm
    long long hash = 5381;
    int c;
    char *str = data_chunk;

    while ((c = *str++)) {
        hash = ((hash << 5) + hash) + c; // hash * 33 + c
    }

    return recursive_chain_hash(hash, steps_left - 1);
}

void process(Record* rec, int steps) {
    rec->base_value += 5;
    rec->processing_count++;
    // Apply some computationally intensive transformation
    long long final_hash = recursive_chain_hash(rec->base_value, steps);
    rec->last_result = final_hash;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <record_id> <steps>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    int target_id = atoi(argv[1]);
    int steps = atoi(argv[2]);

    if (target_id < 0 || target_id >= NUM_RECORDS) {
        fprintf(stderr, "Invalid record ID.\n");
        exit(EXIT_FAILURE);
    }

    int fd = shm_open(SHM_NAME, O_RDWR, 0666);
    if (fd == -1) {
        perror("shm_open failed");
        exit(EXIT_FAILURE);
    }

    RecordDB *db = mmap(NULL, sizeof(RecordDB), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    Record *rec = &db->records[target_id];

    printf("[Worker PID:%d] Locking record %d...\n", getpid(), target_id);

    // BEGIN CRITICAL SECTION

    int lock_res = record_db_lock(db, rec);

    if (lock_res == EOWNERDEAD) {
        printf("\033[1;31m[Worker PID:%d] WARNING: Previous owner died holding the lock! Recovering...\033[0m\n", getpid());
        pthread_mutex_consistent(&rec->mtx);
        printf("[Worker PID:%d] Mutex state recovered and locked. Proceeding...\n", getpid());
    } else if (lock_res != 0) {
        fprintf(stderr, "pthread_mutex_lock failed with code %d\n", lock_res);
        exit(EXIT_FAILURE);
    }

    printf("[Worker PID:%d] Locked record %d. Starting calculations...\n", getpid(), target_id);
    printf("   -> Current base_value: %lld, processing_count: %d\n",
               rec->base_value, rec->processing_count);

    process(rec, steps);

    printf("[Worker PID:%d] Success! Record %d last result updated to: %lld\n", getpid(), target_id, rec->last_result);

    record_db_unlock(db, rec);
    // END CRITICAL SECTION

    printf("[Worker PID:%d] Unlocked record %d!\n", getpid(), target_id);

    munmap(db, sizeof(RecordDB));
    close(fd);

    return 0;
}
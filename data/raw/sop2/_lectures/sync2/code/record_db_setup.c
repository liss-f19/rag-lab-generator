#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <pthread.h>

#include "record_db.h"

int main() {
    shm_unlink(SHM_NAME);

    int fd = shm_open(SHM_NAME, O_CREAT | O_RDWR | O_EXCL, 0666);
    if (fd == -1) {
        perror("shm_open failed");
        exit(EXIT_FAILURE);
    }

    if (ftruncate(fd, sizeof(RecordDB)) == -1) {
        perror("ftruncate failed");
        exit(EXIT_FAILURE);
    }

    RecordDB *db = mmap(NULL, sizeof(RecordDB), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);

    // Initialize shared mutexes
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
#ifdef RECORD_DB_ROBUST
    pthread_mutexattr_setrobust(&attr, PTHREAD_MUTEX_ROBUST);
#endif

#ifdef RECORD_DB_GLOBAL_LOCK
    pthread_mutex_init(&db->global_mtx, &attr);
#endif
    for (int i = 0; i < NUM_RECORDS; i++) {
        pthread_mutex_init(&db->records[i].mtx, &attr);
        db->records[i].id = i;
        db->records[i].base_value = 100 + i; // Inicjalizujemy jakimiś danymi
        db->records[i].last_result = 0;
        db->records[i].processing_count = 0;
    }

    pthread_mutexattr_destroy(&attr);
    munmap(db, sizeof(RecordDB));
    close(fd);

    printf("[Setup] Database initialized with %d records.\n", NUM_RECORDS);
    return 0;
}
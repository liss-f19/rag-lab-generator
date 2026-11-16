#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>

#define NUM_READERS 5
#define NUM_WRITERS 2

// Shared state
int shared_data = 0;

int readers_count = 0;
int writers_count = 0;

pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t cv = PTHREAD_COND_INITIALIZER;

void* writer(void* arg) {
    int id = *(int*)arg;

    while (1) {
        sleep(2); // Pisarz nie pisze non-stop, daje szansę czytelnikom

        // Writer entry section
        pthread_mutex_lock(&mtx);
        while (readers_count > 0 || writers_count > 0) {
            // Wait until all are out
            pthread_cond_wait(&cv, &mtx);
        }
        writers_count++;
        pthread_mutex_unlock(&mtx);

        shared_data += 10;
        printf("\033[1;31m[Writer %d] Updates shared value to: %d\033[0m\n", id, shared_data);
        usleep(500000); // Symulacja czasu zapisu

        // Writer exit section
        pthread_mutex_lock(&mtx);
        writers_count--;

        pthread_cond_broadcast(&cv);
        pthread_mutex_unlock(&mtx);
    }
    return NULL;
}

void* reader(void* arg) {
    int id = *(int*)arg;

    while (1) {
        usleep(100000); // Czytelnicy czytają bardzo często

        // Reader entry section
        pthread_mutex_lock(&mtx);
        while (writers_count > 0) {
            // Wait until writer is out
            pthread_cond_wait(&cv, &mtx);
        }
        readers_count++;
        pthread_mutex_unlock(&mtx);


        printf("\033[1;32m[Reader %d] Shared value: %d\033[0m\n", id, shared_data);
        usleep(200000);

        // Reader exit section
        pthread_mutex_lock(&mtx);
        readers_count--;
        if (readers_count == 0) {
            pthread_cond_signal(&cv);
        }
        pthread_mutex_unlock(&mtx);
    }
    return NULL;
}

int main() {
    pthread_t readers[NUM_READERS];
    pthread_t writers[NUM_WRITERS];
    int reader_ids[NUM_READERS];
    int writer_ids[NUM_WRITERS];

    printf("Rozpoczynam symulacje (Wcisnij Ctrl+C aby przerwac)...\n");

    for (int i = 0; i < NUM_READERS; i++) {
        reader_ids[i] = i + 1;
        pthread_create(&readers[i], NULL, reader, &reader_ids[i]);
    }

    for (int i = 0; i < NUM_WRITERS; i++) {
        writer_ids[i] = i + 1;
        pthread_create(&writers[i], NULL, writer, &writer_ids[i]);
    }

    for (int i = 0; i < NUM_READERS; i++) {
        pthread_join(readers[i], NULL);
    }
    for (int i = 0; i < NUM_WRITERS; i++) {
        pthread_join(writers[i], NULL);
    }

    return 0;
}
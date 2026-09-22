#include <fcntl.h>
#include <semaphore.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define CYCLES 5
#define READINGS_PER_CYCLE 10

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <sensor_id>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    int sensor_id = atoi(argv[1]);

    srand(getpid());

    // Open existing semaphores
    sem_t *data_ready = sem_open("/data_ready", 0);
    sem_t *can_overwrite = sem_open("/can_overwrite", 0);

    if (data_ready == SEM_FAILED || can_overwrite == SEM_FAILED) {
        perror("sem_open failed (is aggregator running?)");
        exit(EXIT_FAILURE);
    }

    char filename[32];
    snprintf(filename, sizeof(filename), "sensor_%d.dat", sensor_id);

    printf("[Sensor %d] Started. Writing to '%s'\n", sensor_id, filename);

    for (int i = 1; i <= CYCLES; i++) {
        FILE *file = fopen(filename, "w");
        if (file) {
            for (int r = 0; r < READINGS_PER_CYCLE; r++) {
                // Generate random temp between 15.0 and 35.0
                float temp = 15.0f + ((float)rand() / RAND_MAX) * 20.0f;
                fprintf(file, "%.2f\n", temp);
                usleep(rand() % 1000000);
            }
            fclose(file);
        }

        printf("[Sensor %d] Cycle %d: Wrote %d readings to %s.\n",
               sensor_id, i, READINGS_PER_CYCLE, filename);

        // Signal aggregator that data is ready
        sem_post(data_ready);

        // Wait for permission to start the next cycle
        sem_wait(can_overwrite);
    }

    // Cleanup (close only)
    sem_close(data_ready);
    sem_close(can_overwrite);

    printf("[Sensor %d] Finished.\n", sensor_id);
    return 0;
}

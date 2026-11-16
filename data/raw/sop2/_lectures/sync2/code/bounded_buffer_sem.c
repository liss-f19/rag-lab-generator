#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <semaphore.h>

#define BUFFER_SIZE 5
#define NUM_PRODUCERS 2
#define NUM_CONSUMERS 2
#define ITEMS_PER_PRODUCER 10

typedef struct bounded_buffer {
    int items[BUFFER_SIZE];
    int in;
    int out;
    sem_t mtx;
    sem_t empty;
    sem_t nonempty;
} bounded_buffer_t;

void producer(bounded_buffer_t *buf, int id) {
    for (int i = 0; i < ITEMS_PER_PRODUCER; i++) {
        int item = (id * 100) + i; // Generate some unique data

        sem_wait(&buf->empty);     // Wait for empty slot
        sem_wait(&buf->mtx);       // Lock buffer

        buf->items[buf->in] = item;
        printf("[Producer %d] Produced: %d at index %d\n", id, item, buf->in);
        buf->in = (buf->in + 1) % BUFFER_SIZE;

        sem_post(&buf->mtx);       // Unlock buffer
        sem_post(&buf->nonempty);  // Signal that a new item is available

        usleep(100000); // Simulate work
    }
}

void consumer(bounded_buffer_t *buf, int id) {
    int items_to_consume = (NUM_PRODUCERS * ITEMS_PER_PRODUCER) / NUM_CONSUMERS;

    for (int i = 0; i < items_to_consume; i++) {
        sem_wait(&buf->nonempty);  // Wait for available item
        sem_wait(&buf->mtx);       // Lock buffer

        int item = buf->items[buf->out];
        printf("[Consumer %d] Consumed: %d from index %d\n", id, item, buf->out);
        buf->out = (buf->out + 1) % BUFFER_SIZE;

        sem_post(&buf->mtx);       // Unlock buffer
        sem_post(&buf->empty);     // Signal that a slot is empty

        usleep(150000); // Simulate work
    }
}

int main() {
    // 1. Create anonymous shared memory for the buffer
    bounded_buffer_t *buf = mmap(NULL, sizeof(bounded_buffer_t),
                                 PROT_READ | PROT_WRITE,
                                 MAP_SHARED | MAP_ANONYMOUS, -1, 0);

    if (buf == MAP_FAILED) {
        perror("mmap failed");
        exit(EXIT_FAILURE);
    }

    // 2. Initialize buffer indices
    buf->in = 0;
    buf->out = 0;

    // 3. Initialize unnamed semaphores
    // The second argument (pshared) is 1, indicating the semaphore is shared between processes
    sem_init(&buf->mtx, 1, 1);              // Mutex for buffer access
    sem_init(&buf->empty, 1, BUFFER_SIZE);  // Counts empty slots
    sem_init(&buf->nonempty, 1, 0);         // Counts filled slots

    // 4. Fork Producers
    for (int i = 0; i < NUM_PRODUCERS; i++) {
        if (fork() == 0) {
            producer(buf, i);
            exit(EXIT_SUCCESS);
        }
    }

    // 5. Fork Consumers
    for (int i = 0; i < NUM_CONSUMERS; i++) {
        if (fork() == 0) {
            consumer(buf, i);
            exit(EXIT_SUCCESS);
        }
    }

    // 6. Wait for all child processes to finish
    int total_children = NUM_PRODUCERS + NUM_CONSUMERS;
    for (int i = 0; i < total_children; i++) {
        wait(NULL);
    }

    // 7. Cleanup
    sem_destroy(&buf->mtx);
    sem_destroy(&buf->empty);
    sem_destroy(&buf->nonempty);
    munmap(buf, sizeof(bounded_buffer_t));

    printf("[Main] All done. Shared memory cleaned up.\n");
    return 0;
}

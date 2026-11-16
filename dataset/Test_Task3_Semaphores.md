# Task 3: Semaphores (10 points)

There are three processes in the system: P1, P2, and P3. Each has a function, operating on the same instance of shared data, named `s1()`, `s2()`, and `s3()`, respectively. Using semaphores with the presented API, synchronize the processes, ensuring the order in which those sections are executed, regardless of the process startup order and/or system load:

S1 → S2 → S3 → S1 → S2 → S3 → ...

```c
void sem_init(sem, v); // Creates semaphore with given name (string)
                       // and initial value v. No-op if already exists.
void sem_wait(sem);    // Decrements semaphore value blocking if 0
void sem_post(sem);    // Increments semaphore value
int  sem_getval(sem);  // Returns current value of the semaphore
```

Semaphores are identified by names (`sem`). All functions can be called concurrently.

**Write pseudocode for processes P1, P2, and P3.**

---


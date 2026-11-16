# Task 2: Critical section (10 points)

*Operating Systems 2 — Lecture Test 1 - Retake — 29 April 2025 — Page 2 of 6*

Take a look at the following attempt to solve the critical section problem for processes P0, ..., Pn; Assume that the shared variable `who` is initialized to -1 before processes are started.

```c
#define Pk ... // equals k in Pk
/* ... */
while (who != -1) { } // entry section
who = Pk;
/* critical section */
who = -1; // exit section
/* ... */
```

Assume that the memory stores and loads are atomic. Check if this code satisfies **all** the required conditions for a correct critical section problem solution. **For each condition**, give a short explanation on why it is satisfied or not.

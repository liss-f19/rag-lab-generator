---
title: "Slides"
type: presentation
---

# Shared Memory

Operating Systems 2 Lecture

---

### What is `mmap()`?

It maps a file into the address space.

```c
/* --- not a slide separator --- */
void *p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, 0);
```

---

A slide without any heading at all.

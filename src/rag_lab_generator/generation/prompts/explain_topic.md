Explain the topic to a student of {course} who is preparing for the laboratory: {topic}

Depth: {depth}. `short` means a compact explanation of at most 15 lines; `full` means a complete
walk-through with every section below.

Retrieved course material:

---
{context}
---

Structure the answer as:

1. **Definition** - what the mechanism is, in two or three sentences, in the terms the course uses.
2. **Why it matters** - the concrete problem in the laboratory that this mechanism solves.
3. **Minimal example** - the smallest complete C fragment that shows the API in use, inside a fenced
   `c` code block, with the required error checks and every header it needs. Use only functions that
   appear in the retrieved material.
4. **Common mistakes** - three to five mistakes students actually make with this API, each one line,
   each saying what breaks as a consequence.
5. **Man pages** - the exact pages to read, in the course notation, for example `man 3p fstatat`.
6. **Self-check** - one or two questions the student should be able to answer before the laboratory.

Never invent an API, a flag or a structure field. If the retrieved material does not cover part of
the topic, say which part is missing and name the man page that covers it.

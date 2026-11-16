Draw a diagram of this Operating Systems concept for a student of the course: {concept}

Requested diagram type: {diagram_type} (one of `flowchart`, `sequenceDiagram`, `stateDiagram`).

Retrieved course material:

---
{context}
---

Output rules:

- Output ONLY one fenced code block tagged `mermaid`, followed by a legend of two or three
  sentences. Nothing else, no heading, no preamble.
- The diagram must show the real mechanism, not a generic picture: name the system calls on the
  edges (`fork()`, `execvp()`, `waitpid()`, `write()`, `epoll_wait()`), name the processes, the file
  descriptors and the kernel objects involved, and mark where a call blocks or returns an error.
- `flowchart TD` for control flow and data flow (for example a pipe between two processes),
  `sequenceDiagram` for interactions in time between processes, threads or a client and a server,
  `stateDiagram-v2` for the lifecycle of one object (a process, a connection, a file descriptor).
- Keep node labels short; put the details in the legend.
- Use only identifiers and calls that appear in the retrieved material.

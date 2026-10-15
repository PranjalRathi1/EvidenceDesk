"""Synthetic sample study documents used for the demo workflow and the evaluation
dataset. Generated programmatically (not scraped course material) so there are no
copyright/privacy concerns about shipping them in the repo. One page == one topic,
by design, so evaluation labels can reference exact expected page numbers.
"""
import fitz  # PyMuPDF

OS_NOTES = [
    ("Introduction to Operating Systems and Processes", """
An operating system (OS) is the software layer that manages hardware resources and
provides services to application programs. A process is a running instance of a
program; it has its own address space, a program counter, registers, and a set of
open file descriptors. The OS is responsible for creating, scheduling, and
terminating processes, as well as isolating one process's memory from another's.

Each process moves through states during its lifetime: new, ready, running,
waiting (blocked), and terminated. A process in the ready state is waiting for the
CPU scheduler to give it a time slice; a process in the waiting state is blocked on
an I/O operation or another event and cannot run even if given the CPU.
"""),
    ("Process Scheduling: FCFS and SJF", """
First-Come, First-Served (FCFS) scheduling runs processes strictly in the order
they arrive in the ready queue. FCFS is simple to implement but can cause the
"convoy effect," where a long process at the front of the queue makes many short
processes behind it wait, increasing average waiting time.

Shortest Job First (SJF) scheduling instead picks the ready process with the
smallest estimated run time next. SJF minimizes average waiting time among
non-preemptive scheduling algorithms when job lengths are known in advance, but it
requires predicting run time and can starve long jobs if short jobs keep arriving.
"""),
    ("Process Scheduling: Round Robin and Priority Scheduling", """
Round Robin (RR) scheduling gives each ready process a fixed time slice, called a
quantum, and cycles through the ready queue. RR is preemptive: if a process does
not finish within its quantum, it is moved to the back of the queue. A small
quantum improves responsiveness but increases context-switch overhead; a large
quantum makes RR behave more like FCFS.

Priority scheduling assigns each process a priority number and always runs the
highest-priority ready process. Without safeguards, priority scheduling can starve
low-priority processes indefinitely; a common fix is "aging," which gradually
increases the priority of processes that have waited a long time.
"""),
    ("Deadlocks: Conditions and Prevention", """
A deadlock occurs when a set of processes are each waiting for a resource held by
another process in the set, so none of them can proceed. Four conditions must all
hold simultaneously for a deadlock to occur: mutual exclusion, hold-and-wait, no
preemption, and circular wait.

Deadlocks can be prevented by denying at least one of these four conditions. For
example, requiring processes to request all resources at once denies hold-and-wait,
and imposing a strict global ordering on resource acquisition denies circular wait.
Deadlock avoidance algorithms, such as the Banker's Algorithm, instead grant
requests dynamically only if the resulting state is still safe.
"""),
    ("Virtual Memory and Paging", """
Virtual memory lets each process address more memory than is physically installed,
and gives each process the illusion of a private, contiguous address space. The OS
divides virtual addresses into fixed-size pages and physical memory into
same-sized frames, maintaining a page table that maps pages to frames.

When a process accesses a page that is not currently in a physical frame, a page
fault occurs and the OS loads the page from disk (the backing store). If physical
memory is full, the OS must evict a page using a replacement policy such as Least
Recently Used (LRU) or the clock algorithm, which approximates LRU more cheaply.
"""),
    ("Segmentation and File Systems", """
Segmentation divides a process's address space into logically meaningful variable
sized units, such as code, stack, and heap segments, rather than fixed-size pages.
Segmentation can be combined with paging, giving each segment its own page table.

A file system organizes persistent storage into files and directories and tracks,
for each file, where its data blocks live on disk. Most file systems use an index
structure, such as an inode, to record a file's metadata and the block pointers
needed to read its contents, and directories map human-readable names to these
index structures.
"""),
]

DB_NOTES = [
    ("Introduction to Database Systems and ACID Properties", """
A relational database organizes data into tables of rows and columns and is
usually queried using SQL. Transactions group multiple operations so they behave
as a single unit of work, and relational databases guarantee the ACID properties
for transactions: Atomicity, Consistency, Isolation, and Durability.

Atomicity means a transaction either fully completes or has no effect at all.
Consistency means a transaction moves the database from one valid state to another,
respecting all constraints. Isolation means concurrent transactions do not see each
other's uncommitted intermediate states. Durability means that once a transaction
commits, its effects survive even a subsequent crash.
"""),
    ("Normalization: 1NF, 2NF, and 3NF", """
Normalization is the process of structuring tables to reduce redundancy and avoid
update anomalies. First Normal Form (1NF) requires that every column hold a single
atomic value and that rows have no repeating groups.

Second Normal Form (2NF) requires 1NF plus that every non-key column depends on
the entire primary key, not just part of a composite key. Third Normal Form (3NF)
requires 2NF plus that every non-key column depends only on the primary key and not
on another non-key column (eliminating transitive dependencies).
"""),
    ("Indexing and B-Trees", """
An index is an auxiliary data structure that lets a database find rows matching a
condition without scanning the entire table. Most relational databases implement
indexes using a B-tree or one of its variants, such as the B+ tree.

A B-tree keeps its keys sorted and balanced so that lookups, insertions, and
deletions all take logarithmic time relative to the number of rows. B+ trees store
all actual data (or row pointers) in the leaf nodes and link the leaves together,
which makes range scans over sorted keys efficient.
"""),
    ("SQL Joins", """
A join combines rows from two or more tables based on a related column. An INNER
JOIN returns only the rows that have matching values in both tables. A LEFT (OUTER)
JOIN returns all rows from the left table, with NULLs filling in columns from the
right table when there is no match.

A RIGHT JOIN is the mirror image of a LEFT JOIN, keeping all rows from the right
table. A FULL OUTER JOIN keeps all rows from both tables, filling in NULLs on
whichever side lacks a match.
"""),
    ("Transactions and Concurrency Control", """
When multiple transactions run concurrently, a database must prevent problems such
as dirty reads (reading another transaction's uncommitted data), lost updates, and
non-repeatable reads. Isolation levels, such as Read Committed, Repeatable Read,
and Serializable, trade off strictness against concurrency.

Two common concurrency-control techniques are locking, where a transaction
acquires locks on the rows or tables it touches before releasing them at commit,
and multiversion concurrency control (MVCC), where readers see a consistent
snapshot of the data without blocking writers.
"""),
    ("CAP Theorem and NoSQL Databases", """
The CAP theorem states that a distributed data store can provide at most two of
three guarantees at the same time during a network partition: Consistency (every
read sees the latest write), Availability (every request gets a response), and
Partition tolerance (the system keeps working despite network partitions).

NoSQL databases, such as document stores, key-value stores, and wide-column
stores, often relax strict consistency in favor of availability and horizontal
scalability, compared to traditional single-node relational databases.
"""),
]

BIO_NOTES = [
    ("Cell Structure and the Cell Membrane", """
All living cells are enclosed by a cell membrane, a selectively permeable
phospholipid bilayer studded with embedded proteins. The membrane controls which
substances enter and leave the cell, using passive diffusion for small nonpolar
molecules and membrane transport proteins (channels and pumps) for ions and large
or polar molecules.

Eukaryotic cells additionally contain a nucleus, which houses the cell's DNA, and
membrane-bound organelles such as the endoplasmic reticulum and Golgi apparatus,
which modify and transport proteins.
"""),
    ("Mitochondria and Cellular Respiration", """
Mitochondria are the organelles primarily responsible for producing ATP, the
cell's main energy currency, through cellular respiration. Cellular respiration
breaks down glucose in the presence of oxygen through glycolysis, the citric acid
(Krebs) cycle, and the electron transport chain, yielding far more ATP per glucose
molecule than fermentation alone.

Mitochondria have their own circular DNA and a double membrane; the inner membrane
is folded into cristae, which increase the surface area available for the electron
transport chain.
"""),
    ("Photosynthesis", """
Photosynthesis is the process by which plants, algae, and some bacteria convert
light energy into chemical energy stored in glucose, using carbon dioxide and
water as inputs and releasing oxygen as a byproduct. It occurs in chloroplasts and
has two stages: the light-dependent reactions, which occur in the thylakoid
membrane and produce ATP and NADPH, and the light-independent reactions (the Calvin
cycle), which occur in the stroma and use that ATP and NADPH to fix carbon dioxide
into glucose.

Photosynthesis and cellular respiration are, in a simplified sense, chemically
complementary processes: one stores energy from light into glucose, and the other
releases that stored energy from glucose.
"""),
    ("DNA Structure and Replication", """
DNA is a double helix made of two complementary strands of nucleotides, held
together by hydrogen bonds between base pairs: adenine pairs with thymine, and
guanine pairs with cytosine. This complementary base pairing is the basis for
accurate DNA replication.

During replication, the enzyme helicase unwinds the double helix, and DNA
polymerase synthesizes a new complementary strand from each original strand,
producing two identical double-stranded DNA molecules. Because each new molecule
retains one original strand and gains one new strand, this mechanism is called
semiconservative replication.
"""),
    ("Mitosis", """
Mitosis is the process by which a single eukaryotic cell divides to produce two
genetically identical daughter cells, each with the same number of chromosomes as
the parent cell. It proceeds through prophase (chromosomes condense), metaphase
(chromosomes align at the cell's equator), anaphase (sister chromatids separate
and move to opposite poles), and telophase (two new nuclei form).

Mitosis is used for growth, tissue repair, and asexual reproduction in many
organisms, and it is distinct from meiosis, which produces genetically varied
reproductive cells.
"""),
    ("Meiosis and Protein Synthesis", """
Meiosis is a specialized form of cell division that produces four genetically
distinct haploid gametes from one diploid cell, through two successive divisions
(meiosis I and meiosis II) and a single round of DNA replication. Crossing over
during meiosis I, where homologous chromosomes exchange genetic material, is a
major source of genetic variation.

Protein synthesis converts genetic information into functional proteins in two
stages: transcription, where RNA polymerase copies a gene's DNA sequence into
messenger RNA (mRNA) in the nucleus, and translation, where a ribosome reads the
mRNA in the cytoplasm and assembles the corresponding chain of amino acids.
"""),
]

DOCUMENT_DEFS = {
    "operating_systems_notes.pdf": OS_NOTES,
    "database_systems_notes.pdf": DB_NOTES,
    "cell_biology_notes.pdf": BIO_NOTES,
}


def build_pdf_bytes(title: str, sections: list[tuple[str, str]]) -> bytes:
    doc = fitz.open()
    for heading, body in sections:
        page = doc.new_page(width=612, height=792)
        margin = 54
        y = margin
        page.insert_text((margin, y), title, fontsize=10, fontname="helv", color=(0.4, 0.4, 0.4))
        y += 24
        page.insert_text((margin, y), heading, fontsize=15, fontname="helv")
        y += 28
        rect = fitz.Rect(margin, y, 612 - margin, 792 - margin)
        page.insert_textbox(rect, body.strip(), fontsize=11, fontname="helv")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_all(out_dir) -> list[str]:
    from pathlib import Path

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, sections in DOCUMENT_DEFS.items():
        title = filename.replace("_", " ").replace(".pdf", "").title()
        pdf_bytes = build_pdf_bytes(title, sections)
        path = out_dir / filename
        path.write_bytes(pdf_bytes)
        written.append(str(path))
    return written


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "sample_documents"
    for p in generate_all(target):
        print(p)

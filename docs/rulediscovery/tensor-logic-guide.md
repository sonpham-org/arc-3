# Tensor Logic: compact guide

Source: Pedro Domingos, "Tensor Logic: The Language of AI", arXiv 2510.12269v3 (16 Oct 2025), 17 pages.
Files: `tensor-logic-2510.12269.pdf` (downloaded 24-Sep-2026), `tensor-logic.txt` (pdftotext -layout).
Project site named in the paper: tensor-logic.org. Guide written by Bubba (Claude Opus 5.5) for OpenMind, #arc-3.

## 1. The one idea
A **relation is a sparse Boolean tensor**, and a **Datalog rule is an einsum followed by a step function**.
- `Aunt(x,z) <- Sister(x,y), Parent(y,z)` equals `A[x,z] = H( sum_y S[x,y] P[y,z] )`, with H(v) = 1 if v > 0.
- Join = multiply tensors on shared indices. Projection = sum out the indices missing from the left-hand side.
- Swap Booleans for reals and H for a sigmoid or relu and the same equation is a neural layer.
So logic programming and tensor algebra differ only in the atomic data type. That is the whole unification.

## 2. The language
- The only construct is the **tensor equation**: LHS tensor = optional nonlinearity( joins of RHS tensors ),
  with projection onto the LHS indices. Equations with the same LHS are summed. Elements default to 0.
- Examples: perceptron `Y = step(W[i] X[i])`; MLP `X[i,j] = sig(W[i,j,k] X[i-1,k])`;
  RNN `X[i,*t+1] = sig(W[i,j] X[j,*t] + V[i,j] U[j,t])` (`*t` = virtual index, no memory; RNNs make it Turing complete).
- Syntactic sugar: index functions (`t+1`, `x+dx`), softmax/normalisation, concat, alternative projections
  (`max=`, `avg=`), slices, procedural attachment. Datalog syntax is accepted; parentheses mean Boolean.
- Conditionals: join an expression with a Boolean condition tensor (as in the positional-encoding line).

## 3. Inference and learning
- **Forward chaining**: run the equations as linear code repeatedly until nothing new (fixpoint).
- **Backward chaining**: each equation is a function; the query calls its RHS recursively; unknown = 0.
- **Learning**: the derivative of the LHS with respect to one RHS tensor is the product of the other RHS tensors,
  so the gradient of a tensor logic program is itself a tensor logic program. Different examples can use
  different equations: backpropagation through structure (backpropagation through time is its special case).
- **One equation covers every rule with the same join structure**: learning its weights learns a set of rules
  (an MLP can represent any set of propositional rules).
- **Predicate invention = tensor decomposition**: learning `A[i,j,k] = M[i,p] M'[j,q] M''[k,r] C[p,q,r]` is a
  Tucker decomposition; thresholding the learned factors to Booleans gives invented predicates (hidden relations).

## 4. Other paradigms written as tensor equations
- Convolution `F[x,y] = relu(Filter[dx,dy,ch] Image[x+dx,y+dy,ch])`; pooling `P[x/S,y/S] = F[x,y]`.
- Graph neural network (Table 1): `Agg[n,l,d] = Neig(n,n') Z[n',l,d]`, update with W_Agg and W_Self; node,
  edge and graph classification heads.
- Transformer in about a dozen equations (Table 2): `Comp[b,h,p,p'.] = softmax(Query Key / sqrt(Dk))`, `Attn = Comp Val`.
- Kernel machine `Y[Q] = f(A[i] Y[i] K[Q,i] + B)`; polynomial and Gaussian kernels as equations.
- Graphical models (Table 3): factor = tensor, marginalisation = projection, pointwise product = join,
  join tree = tree-shaped program, belief propagation = forward chaining, sampling = selective projection.

## 5. Reasoning in embedding space (the paper's main new idea)
- Objects get embeddings `Emb[x,d]`. A set is `S[d] = V[x] Emb[x,d]`; membership test `S[d] Emb[A,d]` is about 1
  or about 0, error shrinking with dimension (like a Bloom filter).
- A relation is embedded as the superposition of tensor products: `EmbR[i,j] = R(x,y) Emb[x,i] Emb[y,j]`
  (Smolensky's tensor product representation). Query `D[A,B] = EmbR[i,j] Emb[A,i] Emb[B,j]` recovers R(A,B)
  because random embeddings are nearly orthogonal. Relation symbols can be embedded too, so a whole
  database becomes one rank-3 tensor of (relation, argument, value) triples.
- Rules are embedded by replacing each antecedent and consequent with its embedding; chaining then runs in
  embedding space. Threshold and re-embed periodically to remove accumulated noise.
- With **learned** embeddings, `Sim[x,x'] = Emb[x,d] Emb[x',d]` lets similar objects borrow each other's
  inferences: analogical reasoning. A sigmoid with **temperature T** per equation: T = 0 is purely deductive
  (no hallucination), higher T is increasingly analogical. T can differ per rule (hard truths at 0, weak
  evidence higher). Every intermediate tensor can be read out, so reasoning is transparent.

## 6. Scaling
Dense parts on GPU; sparse parts either through a database query engine (tensors as relations, query
optimisation), or everything on GPU after a (even random) Tucker decomposition into dense embeddings, with
a small, controllable error cleaned up by step functions.

## 7. Link to our work (ARC-3, OpenMind's rule-discovery agent)
- Our phasor vectors are a relative of section 5: binding by elementwise product on phasors is a compressed
  tensor product (holographic reduced representation); the paper uses full tensor products.
- The agent's hand-written rule templates (rules.py, hypotheses.py) are fixed join structures; tensor logic
  says to fix only the join structure and learn the weights, then threshold back into readable rules.
- Ideas for integration: see the provenance entry for this guide and the #arc-3 reply of 24-Sep-2026.

## 8. Ideas: rule LEARNING with tensor logic for the ARC agent (24-Sep-2026, for OpenMind)
1. Join-structure bank, sparse weights: a few equations predict each object's effect (move dx/dy, vanish,
   recolour, appear, none) from (a) its own features x action, (b) its neighbour in a direction x action,
   (c) a linked object x action. Sparsity / description-length penalty; each surviving weight is one rule.
2. Invented predicates: a hidden layer over object features ("is wall", "is player") feeding the effect
   equations; Tucker factorisation of the effect tensor gives object classes and action classes.
3. Structure by search, weights by gradient: generate join structures from the relation vocabulary
   (ILP-style refinement), fit each by gradient, let the existing MDL posterior choose between them.
4. Per-rule temperature annealing: start soft (learns from few examples, analogical), cool as evidence
   grows; at T = 0 the rule is thresholded into an explicit rule in the RuleSet.
5. Negatives for free: every object that did not change is a negative example on every step.
6. Surprise-driven structure: on a surprising event, backward-chain / take gradients to find which relation
   elements could explain it (switch occupied -> door vanished) and add a structure around them.
7. Time: lagged join over the previous run's moves with a learned soft lag (the lag filter, learned).
8. Priors across games (training games only): empirical Bayes over which join structures matter.
9. Language-model hook: the model writes candidate tensor equations (structure); gradient fits the weights;
   the posterior judges. Weight uncertainty feeds epistemic value in expected free energy.

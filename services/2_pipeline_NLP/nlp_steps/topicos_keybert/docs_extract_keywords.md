## Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docs` | str or List[str] | Required | The document(s) for which to extract keywords/keyphrases |
| `candidates` | List[str] | None | Candidate keywords/keyphrases to use instead of extracting them from the document(s) |
| `keyphrase_ngram_range` | Tuple[int, int] | (1, 1) | Length, in words, of the extracted keywords/keyphrases |
| `stop_words` | str or List[str] | "english" | Stopwords to remove from the document |
| `top_n` | int | 5 | Return the top n keywords/keyphrases |
| `min_df` | int | 1 | Minimum document frequency of a word across all documents |

## Diversification Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_maxsum` | bool | False | Whether to use Max Sum Distance for keyword selection |
| `use_mmr` | bool | False | Whether to use Maximal Marginal Relevance (MMR) for selection |
| `diversity` | float | 0.5 | The diversity of results between 0 and 1 if `use_mmr` is True |
| `nr_candidates` | int | 20 | Number of candidates to consider if `use_maxsum` is True |

## Advanced Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vectorizer` | CountVectorizer | None | Custom CountVectorizer from sklearn |
| `highlight` | bool | False | Whether to print the document with highlighted keywords |
| `seed_keywords` | List[str] or List[List[str]] | None | Seed keywords to guide extraction toward specific topics |
| `doc_embeddings` | np.array | None | Pre-computed document embeddings for efficiency |
| `word_embeddings` | np.array | None | Pre-computed word embeddings for efficiency |
| `threshold` | float | None | Minimum similarity value for LLM integration |

## Key Usage Notes

- **Single vs Multiple Documents**: Pass a string for single document or list for multiple documents
- **Keyphrase Length**: Use `keyphrase_ngram_range=(1, 1)` for single words, `(1, 2)` for words and bigrams, etc.  
- **Diversification**: Choose between `use_mmr` (balances relevance/diversity) or `use_maxsum` (maximizes diversity) 
- **Performance**: Pre-compute embeddings with `extract_embeddings()` when experimenting with different parameters
- **Guided Extraction**: Use `seed_keywords` to steer extraction toward specific topics
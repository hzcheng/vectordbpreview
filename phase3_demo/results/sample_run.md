# Sample Run

## Build

Command:

```bash
python3 phase3_demo/src/build_demo.py
```

Observed output:

```text
Built phase3_demo_docs in phase3_demo/demo.db with 133 documents.
```

## Search

Command:

```bash
python3 phase3_demo/src/search_demo.py
```

Observed output summary:

### Keyword Search
- Query: `PostgreSQL`
- Top results came from the `database` category
- This demonstrates exact term matching

### Vector Search
- Query: `怎么搭建编程环境`
- Top results included:
  - `搭建编程环境后，需要检查解释器版本、依赖和测试工具。`
  - `语义搜索可以找到“配置开发环境”和“搭建编程环境”这种同义表达。`
  - `配置开发环境时，先创建虚拟环境再安装依赖会更稳妥。`
- This demonstrates that vector retrieval can connect `编程环境` and `开发环境`

### Filtered Vector Search
- Query: `怎么做语义搜索`
- Filter: `category=ai`
- Top results stayed inside the `ai` category
- This demonstrates vector recall + metadata filtering

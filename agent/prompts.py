from langchain_core.prompts import PromptTemplate

README_GENERATION_PROMPT = PromptTemplate(
    input_variables=["platform", "title", "difficulty", "url", "tags", "language", "code"],
    template="""You are an expert software engineer and AI code documentation writer.
Generate a comprehensive, beautifully formatted GitHub README.md for the following solved code submission:

Platform/Source: {platform}
Problem/Task Title: {title}
Difficulty: {difficulty}
URL: {url}
Tags: {tags}
Programming Language: {language}

Solution Code:
```{language}
{code}
```

Format the output strictly as markdown with the following sections:
1. `# {title}` - Title with difficulty badge (e.g. `![Easy](https://img.shields.io/badge/Difficulty-Easy-brightgreen)`).
2. `## Problem / Task Description` - Concise description of the problem/task statement and key constraints.
3. `## Approach & Intuition` - Explanation of algorithm, data structures used, and strategy.
4. `## Complexity Analysis` - Bullet points for Time Complexity and Space Complexity with reasoning.
5. `## Solution Code` - The provided solution code block in {language}.

Return ONLY the raw markdown content without enclosing backticks around the whole markdown response.
""",
)

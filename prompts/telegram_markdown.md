You are tasked with formatting text for a Telegram chat, optimizing it for readability on a mobile phone. Your goal is to make the text more digestible and easier to read while fully preserving its original message, meaning and details.

---

Follow these instructions to format the text:

1. Use the following Telegram using only these allowed syntax entities:
  - <b>bold</b>
  - <i>italic</i>
  - <code>code</code>
  - <s>strike trough</s>
  - <u>underline</u>
  - <pre language="c++">code</pre>
2. Replace single or double quoted text to bold markdown. Example: "**TEXT**" should become "<b>TEXT<b>".
3. Split the text into smaller, more digestible sections. Use "----" as a separator between these sections. This will make the text easier to read on a mobile device. Consider splitting text (if it makes sense) only if it is 5 lines long or more.
4. When creating lists, always use numbered lists.
5. Preserve the original meaning of the text. Your task is to reformat without changing its original message details.
6. Optimize the text for mobile phone screen size. This includes:
  - simplifying long paragraphs into a bit shorter ones
  - use simple, down to earth language that is easy to read and to understand
  - adjusting line breaks for better readability
  - adding emojis to replace common words and emphasize topic point
7. Be cautious with using underscore markdown, as using it too much looks bad.


---

When you're done, output your formatted text within <formatted_text> tags. Remember to use the "----" separator between sections. Do not include any explanations or comments outside of the <formatted_text> tags.

---

Here is the text you need to format:

<text_to_format>
{{TEXT_TO_FORMAT}}
</text_to_format>

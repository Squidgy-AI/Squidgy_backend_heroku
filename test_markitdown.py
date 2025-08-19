from markitdown import MarkItDown

# md = MarkItDown(enable_plugins=False) # Set to True to enable plugins
# result = md.convert("female_only.csv")
md = MarkItDown(docintel_endpoint="<document_intelligence_endpoint>") # Set to True to enable plugins
result = md.convert("Smart HSE (EN).pdf")

print(result.text_content)
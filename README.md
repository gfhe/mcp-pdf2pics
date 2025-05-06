PDF转图片列表的程序，其中PDF存储的根路径和输出的根路径为系统配置，程序开发时，包括返回的结果列表，均为相对路径。输出的图片均为超高清图片。

支持的功能：
1. 支持单个PDF转图片列表，支持多个PDF转图片列表。
2. 支持PDF 集合转图片列表。
3. 支持文件夹下全部PDF转图片列表。


如果npx 配置好了，但是一致出现如下的错误：
```
(mcp-pdf2pics) @gfhe ➜ /workspaces/mcp-pdf2pics (main) $ mcp dev pdf2pics.py
[05/06/25 13:46:13] ERROR    npx not found. Please ensure Node.js and npm are properly installed and added to your system PATH. You may need to       cli.py:271
                             restart your terminal after installation.
```

可以尝试先执行 `mcp run pdf2pics.py`
然后再执行`mcp dev pdf2pics.py`
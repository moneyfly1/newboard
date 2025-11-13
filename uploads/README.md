# Uploads 目录说明

此目录用于存储用户上传的文件和系统生成的文件。

## 📁 目录结构

```
uploads/
├── README.md              # 本说明文件
├── config/                # 配置文件
│   ├── system/           # 系统配置
│   ├── user/             # 用户配置
│   └── backup/           # 配置备份
├── avatars/              # 用户头像
│   ├── default/          # 默认头像
│   └── users/            # 用户上传的头像
├── documents/            # 文档文件
│   ├── contracts/        # 合同文档
│   ├── invoices/         # 发票文档
│   └── reports/          # 报告文档
├── images/               # 图片文件
│   ├── products/         # 产品图片
│   ├── banners/          # 横幅图片
│   └── icons/            # 图标文件
├── logs/                 # 日志文件
│   ├── access/           # 访问日志
│   ├── error/            # 错误日志
│   └── system/           # 系统日志
└── temp/                 # 临时文件
    ├── uploads/          # 上传临时文件
    └── cache/            # 缓存文件
```

## 🔒 安全注意事项

1. **文件类型限制**：只允许安全的文件类型
2. **文件大小限制**：设置合理的文件大小上限
3. **路径遍历防护**：防止恶意文件路径
4. **病毒扫描**：对上传文件进行安全检查
5. **访问权限控制**：限制文件访问权限

## 📋 支持的文件类型

### 图片文件
- `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- `.svg` (仅限可信来源)

### 文档文件
- `.pdf`, `.doc`, `.docx`
- `.txt`, `.md`, `.rtf`

### 压缩文件
- `.zip`, `.rar`, `.7z`

## 🚀 使用示例

### 后端文件上传处理
```python
from fastapi import UploadFile, File
from pathlib import Path

async def upload_file(file: UploadFile = File(...)):
    # 检查文件类型
    if not is_safe_file_type(file.filename):
        raise HTTPException(400, "不支持的文件类型")
    
    # 生成安全文件名
    safe_filename = generate_safe_filename(file.filename)
    
    # 保存文件
    upload_path = Path("uploads") / "temp" / "uploads" / safe_filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(upload_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return {"filename": safe_filename, "path": str(upload_path)}
```

### 前端文件上传
```javascript
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await fetch('/api/v1/upload/', {
      method: 'POST',
      body: formData
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log('上传成功:', result);
    }
  } catch (error) {
    console.error('上传失败:', error);
  }
}
```

## 🧹 清理策略

1. **临时文件**：定期清理超过24小时的临时文件
2. **日志文件**：保留最近30天的日志文件
3. **缓存文件**：定期清理缓存文件
4. **备份文件**：保留最近7天的配置备份

## 📊 存储配额

- **普通用户**：100MB
- **高级用户**：500MB
- **企业用户**：2GB
- **管理员**：无限制

## 🔧 配置选项

在 `.env` 文件中配置：

```env
# 上传配置
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_FILE_TYPES=jpg,jpeg,png,gif,pdf,doc,docx
UPLOAD_PATH=uploads
TEMP_PATH=uploads/temp
```

## 📝 注意事项

1. 定期备份重要文件
2. 监控磁盘使用情况
3. 设置文件访问日志
4. 定期检查文件完整性
5. 实施文件版本控制

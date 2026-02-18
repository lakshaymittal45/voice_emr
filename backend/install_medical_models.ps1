# 🏥 Voice EMR - Install Medical-Grade Models
# This script helps you install the recommended AI models for medical-grade performance

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   🏥 Voice EMR - Medical Model Installation Wizard" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is installed
Write-Host "Checking Ollama installation..." -ForegroundColor Yellow
try {
    $ollamaVersion = ollama --version 2>&1
    Write-Host "✅ Ollama is installed: $ollamaVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Ollama is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Ollama first:" -ForegroundColor Yellow
    Write-Host "1. Visit: https://ollama.ai/" -ForegroundColor White
    Write-Host "2. Download and install Ollama for Windows" -ForegroundColor White
    Write-Host "3. Restart your computer" -ForegroundColor White
    Write-Host "4. Run this script again" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check currently installed models
Write-Host ""
Write-Host "Checking currently installed models..." -ForegroundColor Yellow
$installedModels = ollama list 2>&1 | Out-String
Write-Host $installedModels -ForegroundColor Gray

# Function to check if a model is installed
function Test-ModelInstalled {
    param($modelName)
    return $installedModels -match $modelName
}

# Check system resources
Write-Host ""
Write-Host "Checking system resources..." -ForegroundColor Yellow
$memory = Get-CimInstance Win32_OperatingSystem
$totalRamGB = [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2)
$freeRamGB = [math]::Round($memory.FreePhysicalMemory / 1MB, 2)

Write-Host "Total RAM: $totalRamGB GB" -ForegroundColor White
Write-Host "Free RAM:  $freeRamGB GB" -ForegroundColor White

# Get free disk space
$drive = Get-PSDrive C
$freeDiskGB = [math]::Round($drive.Free / 1GB, 2)
Write-Host "Free Disk Space (C:): $freeDiskGB GB" -ForegroundColor White

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Choose Installation Profile" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. BEST - Medical-Grade (Recommended)" -ForegroundColor Green
Write-Host "   Model: llama3.1:70b" -ForegroundColor White
Write-Host "   Requirements: 64+ GB RAM, ~40 GB disk space" -ForegroundColor Gray
Write-Host "   Performance: ⭐⭐⭐⭐⭐ Excellent medical reasoning" -ForegroundColor Gray
Write-Host ""

Write-Host "2. BALANCED - Fast & Accurate" -ForegroundColor Yellow
Write-Host "   Model: mixtral:8x7b" -ForegroundColor White
Write-Host "   Requirements: 32+ GB RAM, ~26 GB disk space" -ForegroundColor Gray
Write-Host "   Performance: ⭐⭐⭐⭐ Very good, faster than 70B" -ForegroundColor Gray
Write-Host ""

Write-Host "3. LIGHT - Resource-Friendly" -ForegroundColor Cyan
Write-Host "   Model: llama3.1:8b" -ForegroundColor White
Write-Host "   Requirements: 16+ GB RAM, ~5 GB disk space" -ForegroundColor Gray
Write-Host "   Performance: ⭐⭐⭐⭐ Good for most cases" -ForegroundColor Gray
Write-Host ""

Write-Host "4. MEDICAL SPECIALIST - PubMed-Trained" -ForegroundColor Magenta
Write-Host "   Model: meditron:7b" -ForegroundColor White
Write-Host "   Requirements: 16+ GB RAM, ~4 GB disk space" -ForegroundColor Gray
Write-Host "   Performance: ⭐⭐⭐⭐ Medical literature specialist" -ForegroundColor Gray
Write-Host ""

Write-Host "5. CUSTOM - Choose models manually" -ForegroundColor White
Write-Host ""

Write-Host "6. SKIP - I'll install models later" -ForegroundColor DarkGray
Write-Host ""

# Get user choice
$choice = Read-Host "Enter your choice (1-6)"

switch ($choice) {
    "1" {
        # Best - llama3.1:70b
        if ($totalRamGB -lt 48) {
            Write-Host ""
            Write-Host "⚠️  WARNING: Your system has $totalRamGB GB RAM." -ForegroundColor Red
            Write-Host "   Recommended: 64+ GB for llama3.1:70b" -ForegroundColor Yellow
            Write-Host ""
            $confirm = Read-Host "Continue anyway? (y/N)"
            if ($confirm -ne "y") {
                Write-Host "Installation cancelled. Try option 2 (Balanced) instead." -ForegroundColor Yellow
                exit 0
            }
        }
        
        if ($freeDiskGB -lt 40) {
            Write-Host ""
            Write-Host "❌ ERROR: Insufficient disk space!" -ForegroundColor Red
            Write-Host "   Required: 40 GB | Available: $freeDiskGB GB" -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
        
        if (Test-ModelInstalled "llama3.1:70b") {
            Write-Host ""
            Write-Host "✅ llama3.1:70b is already installed!" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "Installing llama3.1:70b (~40 GB download)..." -ForegroundColor Yellow
            Write-Host "This will take 15-60 minutes depending on your internet speed..." -ForegroundColor Gray
            Write-Host ""
            ollama pull llama3.1:70b
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Successfully installed llama3.1:70b!" -ForegroundColor Green
            } else {
                Write-Host "❌ Installation failed. Check your internet connection." -ForegroundColor Red
            }
        }
    }
    
    "2" {
        # Balanced - mixtral:8x7b
        if ($totalRamGB -lt 24) {
            Write-Host ""
            Write-Host "⚠️  WARNING: Your system has $totalRamGB GB RAM." -ForegroundColor Red
            Write-Host "   Recommended: 32+ GB for mixtral:8x7b" -ForegroundColor Yellow
            Write-Host ""
            $confirm = Read-Host "Continue anyway? (y/N)"
            if ($confirm -ne "y") {
                Write-Host "Installation cancelled. Try option 3 (Light) instead." -ForegroundColor Yellow
                exit 0
            }
        }
        
        if ($freeDiskGB -lt 26) {
            Write-Host ""
            Write-Host "❌ ERROR: Insufficient disk space!" -ForegroundColor Red
            Write-Host "   Required: 26 GB | Available: $freeDiskGB GB" -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
        
        if (Test-ModelInstalled "mixtral:8x7b") {
            Write-Host ""
            Write-Host "✅ mixtral:8x7b is already installed!" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "Installing mixtral:8x7b (~26 GB download)..." -ForegroundColor Yellow
            Write-Host "This will take 10-45 minutes depending on your internet speed..." -ForegroundColor Gray
            Write-Host ""
            ollama pull mixtral:8x7b
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Successfully installed mixtral:8x7b!" -ForegroundColor Green
            } else {
                Write-Host "❌ Installation failed. Check your internet connection." -ForegroundColor Red
            }
        }
    }
    
    "3" {
        # Light - llama3.1:8b
        if ($freeDiskGB -lt 5) {
            Write-Host ""
            Write-Host "❌ ERROR: Insufficient disk space!" -ForegroundColor Red
            Write-Host "   Required: 5 GB | Available: $freeDiskGB GB" -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
        
        if (Test-ModelInstalled "llama3.1:8b") {
            Write-Host ""
            Write-Host "✅ llama3.1:8b is already installed!" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "Installing llama3.1:8b (~5 GB download)..." -ForegroundColor Yellow
            Write-Host ""
            ollama pull llama3.1:8b
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Successfully installed llama3.1:8b!" -ForegroundColor Green
            } else {
                Write-Host "❌ Installation failed. Check your internet connection." -ForegroundColor Red
            }
        }
    }
    
    "4" {
        # Medical Specialist - meditron:7b
        if ($freeDiskGB -lt 5) {
            Write-Host ""
            Write-Host "❌ ERROR: Insufficient disk space!" -ForegroundColor Red
            Write-Host "   Required: 5 GB | Available: $freeDiskGB GB" -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
        
        if (Test-ModelInstalled "meditron:7b") {
            Write-Host ""
            Write-Host "✅ meditron:7b is already installed!" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "Installing meditron:7b (~4 GB download)..." -ForegroundColor Yellow
            Write-Host ""
            ollama pull meditron:7b
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Successfully installed meditron:7b!" -ForegroundColor Green
            } else {
                Write-Host "❌ Installation failed. Check your internet connection." -ForegroundColor Red
            }
        }
    }
    
    "5" {
        # Custom
        Write-Host ""
        Write-Host "Available models:" -ForegroundColor Yellow
        Write-Host "  - llama3.1:70b  (Best, ~40 GB)" -ForegroundColor White
        Write-Host "  - mixtral:8x7b  (Balanced, ~26 GB)" -ForegroundColor White
        Write-Host "  - llama3.1:8b   (Light, ~5 GB)" -ForegroundColor White
        Write-Host "  - meditron:7b   (Medical, ~4 GB)" -ForegroundColor White
        Write-Host ""
        
        $customModels = Read-Host "Enter model names separated by commas (e.g., llama3.1:70b,mixtral:8x7b)"
        
        foreach ($model in $customModels.Split(',')) {
            $model = $model.Trim()
            if ($model) {
                if (Test-ModelInstalled $model) {
                    Write-Host "✅ $model is already installed!" -ForegroundColor Green
                } else {
                    Write-Host ""
                    Write-Host "Installing $model..." -ForegroundColor Yellow
                    ollama pull $model
                    
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "✅ Successfully installed $model!" -ForegroundColor Green
                    } else {
                        Write-Host "❌ Failed to install $model" -ForegroundColor Red
                    }
                }
            }
        }
    }
    
    "6" {
        # Skip
        Write-Host ""
        Write-Host "Installation skipped. You can install models later with:" -ForegroundColor Yellow
        Write-Host "  ollama pull llama3.1:70b" -ForegroundColor White
        Write-Host "  ollama pull mixtral:8x7b" -ForegroundColor White
        Write-Host ""
    }
    
    default {
        Write-Host ""
        Write-Host "Invalid choice. Please run the script again." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Installation Summary" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Currently installed models:" -ForegroundColor Yellow
ollama list

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Next Steps" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Start the backend server:" -ForegroundColor Yellow
Write-Host "   cd backend" -ForegroundColor White
Write-Host "   uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""

Write-Host "2. Check model status:" -ForegroundColor Yellow
Write-Host "   Visit: http://localhost:8000/models/status" -ForegroundColor White
Write-Host ""

Write-Host "3. Test with an audio file" -ForegroundColor Yellow
Write-Host "   The system will automatically use the best available model!" -ForegroundColor White
Write-Host ""

Write-Host "For more information, see: backend/MEDICAL_MODELS_GUIDE.md" -ForegroundColor Gray
Write-Host ""

Read-Host "Press Enter to exit"

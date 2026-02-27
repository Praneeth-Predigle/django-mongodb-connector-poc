Set-Location -LiteralPath 'e:\Pedigle VS Code\mongo-poc'
Write-Output "Working directory: $(Get-Location)"
Write-Output "Checking git version..."
git --version 2>&1 | Write-Output
Write-Output "Initializing git if needed..."
$init = git init 2>&1
Write-Output $init
if (-not (Test-Path -LiteralPath '.gitignore')) {
@'
mongoenv/
venv/
env/
Scripts/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.env
.DS_Store
.idea/
.vscode/
*.sqlite3
'@ | Out-File -Encoding utf8 .gitignore
Write-Output '.gitignore created'
} else {
Write-Output '.gitignore exists'
}
$name = git config user.name
if (-not $name) {
  git config user.name 'RepoUser'
  git config user.email 'repo@example.com'
  Write-Output 'Set local git user.name/email to RepoUser/repo@example.com'
} else {
  Write-Output "git user.name is set: $name"
}
Write-Output 'Staging files...'
git add . 2>&1 | Write-Output
Write-Output 'Committing...'
$commit = git commit -m 'Initial commit' 2>&1
Write-Output "Commit result: $commit"
Write-Output 'Configuring remote...'
git remote remove origin 2>$null
git remote add origin git@github.com:Praneeth-Predigle/django-mongodb-connector-poc.git 2>&1 | Write-Output
Write-Output 'Setting branch to main...'
git branch -M main 2>&1 | Write-Output
Write-Output 'Pushing to origin main...'
$push = git push -u origin main 2>&1
Write-Output "Push result: $push"

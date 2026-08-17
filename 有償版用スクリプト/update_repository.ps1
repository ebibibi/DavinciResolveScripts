# Bring the working copy up to date before a run, and say which version ran.
#
# The scripts live in a Git working copy on the editing machine, so a fix that
# is merged is not a fix that is running. Pulling here removes the manual step
# that was silently skipping releases.
#
# A failed update never stops the run: an edit with a slightly old script is
# worth more than no edit at all. It does have to be loud, because "it did not
# update" and "it updated and still misbehaves" look identical otherwise, and
# guessing wrong sends the next hour into the wrong code.

function Get-RepositoryVersion {
    param([string]$RepositoryRoot)

    $described = & git -C $RepositoryRoot log -1 --format="%h %ad %s" --date=short 2>&1
    if ($LASTEXITCODE -ne 0) {
        return "(unknown)"
    }
    return ($described | Out-String).Trim()
}

function Update-Repository {
    param([string]$RepositoryRoot)

    # git はふつうの進捗をstderrに書く。呼び出し元の ErrorActionPreference が
    # Stop のままだと、成功したpullでも PowerShell 5.1 が例外にしてしまう。
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Host "! gitが見つかりません。更新せずに現在の版で実行します。" -ForegroundColor Yellow
            return $false
        }

        & git -C $RepositoryRoot rev-parse --is-inside-work-tree 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "! Gitの作業コピーではありません。更新せずに実行します: $RepositoryRoot" -ForegroundColor Yellow
            return $false
        }

        $Before = Get-RepositoryVersion -RepositoryRoot $RepositoryRoot

        $Branch = (& git -C $RepositoryRoot rev-parse --abbrev-ref HEAD 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $Branch -ne "main") {
            Write-Host "! ブランチが main ではないため更新しません（$Branch）。現在の版: $Before" -ForegroundColor Yellow
            return $false
        }

        # 追跡ファイルに手を入れている場合は触らない。config.json は .gitignore に
        # あるので、環境ごとの設定はここに出てこない＝設定は消えない。
        $Dirty = (& git -C $RepositoryRoot status --porcelain --untracked-files=no 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $Dirty) {
            Write-Host "! 未コミットの変更があるため更新しません。現在の版: $Before" -ForegroundColor Yellow
            Write-Host $Dirty
            return $false
        }

        Write-Host "最新版を取得しています..." -ForegroundColor Cyan
        # --ff-only: 勝手にマージコミットを作らせない。分岐しているなら人が見る。
        $Output = & git -C $RepositoryRoot pull --ff-only 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Host "! 更新できませんでした。現在の版で実行します: $Before" -ForegroundColor Yellow
            Write-Host $Output.Trim()
            return $false
        }

        $After = Get-RepositoryVersion -RepositoryRoot $RepositoryRoot
        if ($After -eq $Before) {
            Write-Host "✓ すでに最新です: $After" -ForegroundColor Green
            return $true
        }

        Write-Host "✓ 更新しました: $Before -> $After" -ForegroundColor Green
        # 実行中の .ps1 は起動時に読み込み済みなので、ランチャー自身の変更が効くのは
        # 次回から。Pythonはこの後で起動するため、そちらは今回から新しい版で動く。
        Write-Host "  ランチャー自身の変更は次回の実行から反映されます。" -ForegroundColor DarkGray
        return $true
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }
}

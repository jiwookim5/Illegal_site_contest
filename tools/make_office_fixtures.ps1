# 옛 형식 오피스 문서(.doc·.xls·.ppt)와 숨긴 서식을 넣은 .xlsx 시험 파일을 MS Office 로 만든다 (testsite5/files).
# 한 번 만들어 저장소에 넣어 두므로 평소에는 다시 돌릴 필요가 없다. MS Office 가 설치된 PC 에서만 동작한다.
#   powershell -ExecutionPolicy Bypass -File tools\make_office_fixtures.ps1
$ErrorActionPreference = 'Stop'
$out = Join-Path (Split-Path -Parent $PSScriptRoot) 'testsite5\files'

# Word 97-2003 (.doc)
$word = New-Object -ComObject Word.Application
$word.Visible = $false; $word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Add()
  $doc.Content.Text = "구민 의견 수렴 결과`r카지노사이트 가입쿠폰 즉시지급 텔레그램 @doc777`r담당: 기획예산과"
  $doc.SaveAs2([ref](Join-Path $out 'legacy.doc'), [ref]0)          # wdFormatDocument97
  $doc.Close([ref]0)
} finally { $word.Quit() }

# Excel 97-2003 (.xls) 와 숨긴 서식 .xlsx
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Add()
  $ws = $wb.Worksheets.Item(1)
  $ws.Range("A1").Value2 = "사업명"; $ws.Range("A2").Value2 = "마을 도서관 개선"
  $ws.Range("A3").Value2 = "토토사이트 먹튀검증 안전놀이터 카톡 xls777"
  $wb.SaveAs((Join-Path $out 'legacy.xls'), 56)                      # xlExcel8
  $wb.Close($false)

  $wb = $xl.Workbooks.Add()
  while ($wb.Worksheets.Count -lt 2) { [void]$wb.Worksheets.Add([Type]::Missing, $wb.Worksheets.Item($wb.Worksheets.Count)) }
  $ws = $wb.Worksheets.Item(1)
  $ws.Range("A1").Value2 = "2027년 예산 집행 현황"
  $ws.Range("A2").Value2 = "도서관 개선 사업"
  $ws.Range("B2").Value2 = "바카라 에볼루션 첫충 텔레그램 @white77"; $ws.Range("B2").Font.Color = 16777215   # 흰 글꼴
  $ws.Range("B3").Value2 = "급전대출 무직자 당일 승인 카톡 tiny777"; $ws.Range("B3").Font.Size = 1          # 1pt
  $ws.Range("B4").Value2 = "온라인카지노 무료머니 텔레그램 @fmt777"; $ws.Range("B4").NumberFormat = ";;;"   # 값 안 보이게
  $ws.Range("A5").Value2 = "슬롯머신 가입머니 즉시지급 카톡 row777"; $ws.Rows.Item(5).Hidden = $true       # 숨긴 행
  $ws.Range("D2").Value2 = "홀덤 입플 이벤트 텔레그램 @col777"; $ws.Columns.Item(4).Hidden = $true       # 숨긴 열
  $ws2 = $wb.Worksheets.Item(2)
  $ws2.Range("A1").Value2 = "출장안마 24시 후불 카톡 sheet777"; $ws2.Visible = 0                            # 숨긴 시트
  $wb.SaveAs((Join-Path $out 'hidden.xlsx'), 51)                     # xlOpenXMLWorkbook
  $wb.Close($false)
} finally { $xl.Quit() }

# PowerPoint 97-2003 (.ppt)
$pp = New-Object -ComObject PowerPoint.Application
try {
  $pres = $pp.Presentations.Add(0)                                    # 창 없이
  $slide = $pres.Slides.Add(1, 12)                                    # ppLayoutBlank
  [void]$slide.Shapes.AddTextbox(1, 40, 40, 600, 60).TextFrame.TextRange.InsertAfter("주민 참여 예산 설명회")
  [void]$slide.Shapes.AddTextbox(1, 40, 140, 600, 60).TextFrame.TextRange.InsertAfter("비아그라 정품 판매 최저가 텔레그램 @ppt777")
  $pres.SaveAs((Join-Path $out 'legacy.ppt'), 1)                      # ppSaveAsPresentation
  $pres.Close()
} finally { $pp.Quit() }
'OK'

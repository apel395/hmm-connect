from fastapi.responses import Response
from app.services.xlsx_export import build_xlsx


def excel_response(filename, sheets):
    return Response(build_xlsx(sheets), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})

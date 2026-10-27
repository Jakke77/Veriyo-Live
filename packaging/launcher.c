/* A small Unicode launcher for the private, embedded Python runtime. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show) {
    WCHAR root[32768], python[32768], command[32768];
    DWORD length = GetModuleFileNameW(NULL, root, 32768);
    if (!length || length >= 32768) return 1;
    WCHAR *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    if (swprintf(python, 32768, L"%ls\\runtime\\pythonw.exe", root) < 0 ||
        swprintf(command, 32768, L"\"%ls\" \"%ls\\main.py\" %ls", python, root, arguments) < 0) {
        MessageBoxW(NULL, L"Sovelluksen polku tai komentorivi on liian pitkä.", L"Veriyö Live", MB_ICONERROR);
        return 1;
    }
    STARTUPINFOW startup = {0}; startup.cb = sizeof(startup);
    PROCESS_INFORMATION process = {0};
    if (!CreateProcessW(python, command, NULL, NULL, FALSE, 0, NULL, root, &startup, &process)) {
        MessageBoxW(NULL, L"Sovellus ei käynnistynyt. Pura koko ZIP-paketti ennen käynnistystä.\n"
                    L"Lisätietoja saat Tarkista-toiminta.cmd-tiedostolla.", L"Veriyö Live", MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD result = 1; GetExitCodeProcess(process.hProcess, &result);
    CloseHandle(process.hProcess);
    return (int) result;
}

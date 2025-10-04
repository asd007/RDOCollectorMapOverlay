// RDO Map Overlay - Native Windows Launcher
// This launcher starts the Python backend and Electron frontend
// Compile with: cl /EHsc launcher.cpp /Fe:launcher.exe

#include <windows.h>
#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <shlwapi.h>
#include <fstream>

#pragma comment(lib, "shlwapi.lib")

class RDOLauncher {
private:
    std::wstring installPath;
    PROCESS_INFORMATION backendProcess = {0};
    PROCESS_INFORMATION frontendProcess = {0};
    bool debugMode = false;

    std::wstring GetExecutablePath() {
        wchar_t buffer[MAX_PATH];
        GetModuleFileNameW(NULL, buffer, MAX_PATH);
        PathRemoveFileSpecW(buffer);
        return std::wstring(buffer);
    }

    bool CheckDependency(const std::wstring& path, const std::wstring& name) {
        if (!PathFileExistsW(path.c_str())) {
            std::wcerr << L"Error: " << name << L" not found at: " << path << std::endl;
            return false;
        }
        return true;
    }

    bool StartProcess(const std::wstring& executable, const std::wstring& arguments,
                     PROCESS_INFORMATION& processInfo, bool showWindow = false) {
        STARTUPINFOW startupInfo = {0};
        startupInfo.cb = sizeof(startupInfo);

        if (!showWindow) {
            startupInfo.dwFlags = STARTF_USESHOWWINDOW;
            startupInfo.wShowWindow = SW_HIDE;
        }

        std::wstring cmdLine = L"\"" + executable + L"\" " + arguments;

        if (CreateProcessW(
            NULL,
            &cmdLine[0],
            NULL,
            NULL,
            FALSE,
            CREATE_NEW_CONSOLE,
            NULL,
            installPath.c_str(),
            &startupInfo,
            &processInfo
        )) {
            return true;
        }

        DWORD error = GetLastError();
        std::wcerr << L"Failed to start process: " << executable << L" (Error: " << error << L")" << std::endl;
        return false;
    }

    void WaitForPort(int port, int timeoutSeconds = 30) {
        std::wcout << L"Waiting for backend on port " << port << L"..." << std::endl;

        auto startTime = std::chrono::steady_clock::now();
        auto timeout = std::chrono::seconds(timeoutSeconds);

        while (true) {
            SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (sock != INVALID_SOCKET) {
                sockaddr_in addr = {0};
                addr.sin_family = AF_INET;
                addr.sin_port = htons(port);
                addr.sin_addr.s_addr = inet_addr("127.0.0.1");

                if (connect(sock, (sockaddr*)&addr, sizeof(addr)) == 0) {
                    closesocket(sock);
                    std::wcout << L"Backend is ready!" << std::endl;
                    break;
                }
                closesocket(sock);
            }

            if (std::chrono::steady_clock::now() - startTime > timeout) {
                std::wcerr << L"Timeout waiting for backend" << std::endl;
                break;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
    }

    void ShowErrorDialog(const std::wstring& message) {
        MessageBoxW(NULL, message.c_str(), L"RDO Map Overlay - Launch Error", MB_OK | MB_ICONERROR);
    }

public:
    RDOLauncher() {
        // Initialize Winsock for port checking
        WSADATA wsaData;
        WSAStartup(MAKEWORD(2, 2), &wsaData);

        installPath = GetExecutablePath();

        // Check for debug mode
        if (PathFileExistsW((installPath + L"\\debug.txt").c_str())) {
            debugMode = true;
            AllocConsole();
            FILE* pCout;
            freopen_s(&pCout, "CONOUT$", "w", stdout);
            freopen_s(&pCout, "CONOUT$", "w", stderr);
        }
    }

    ~RDOLauncher() {
        Cleanup();
        WSACleanup();
        if (debugMode) {
            FreeConsole();
        }
    }

    bool VerifyInstallation() {
        std::wcout << L"Verifying installation..." << std::endl;

        // Check Python
        std::wstring pythonPath = installPath + L"\\runtime\\python\\python.exe";
        if (!CheckDependency(pythonPath, L"Python runtime")) {
            return false;
        }

        // Check Electron
        std::wstring electronPath = installPath + L"\\electron\\electron.exe";
        if (!CheckDependency(electronPath, L"Electron runtime")) {
            return false;
        }

        // Check backend
        std::wstring backendPath = installPath + L"\\app\\backend\\app.py";
        if (!CheckDependency(backendPath, L"Backend application")) {
            return false;
        }

        // Check frontend
        std::wstring frontendPath = installPath + L"\\app\\main.js";
        if (!CheckDependency(frontendPath, L"Frontend application")) {
            return false;
        }

        std::wcout << L"Installation verified successfully" << std::endl;
        return true;
    }

    bool StartBackend() {
        std::wcout << L"Starting backend..." << std::endl;

        std::wstring pythonPath = installPath + L"\\runtime\\python\\python.exe";
        std::wstring backendPath = installPath + L"\\app\\backend\\app.py";
        std::wstring arguments = L"\"" + backendPath + L"\"";

        if (!StartProcess(pythonPath, arguments, backendProcess, debugMode)) {
            ShowErrorDialog(L"Failed to start backend process.\n\nPlease check that Python dependencies are installed correctly.");
            return false;
        }

        // Wait for backend to be ready
        WaitForPort(5000);
        return true;
    }

    bool StartFrontend() {
        std::wcout << L"Starting frontend..." << std::endl;

        std::wstring electronPath = installPath + L"\\electron\\electron.exe";
        std::wstring appPath = installPath + L"\\app";
        std::wstring arguments = L"\"" + appPath + L"\"";

        if (!StartProcess(electronPath, arguments, frontendProcess, true)) {
            ShowErrorDialog(L"Failed to start Electron frontend.\n\nPlease check that the application files are intact.");
            return false;
        }

        return true;
    }

    void WaitForExit() {
        if (frontendProcess.hProcess) {
            WaitForSingleObject(frontendProcess.hProcess, INFINITE);
        }
    }

    void Cleanup() {
        // Terminate backend when frontend closes
        if (backendProcess.hProcess) {
            TerminateProcess(backendProcess.hProcess, 0);
            CloseHandle(backendProcess.hProcess);
            CloseHandle(backendProcess.hThread);
        }

        if (frontendProcess.hProcess) {
            CloseHandle(frontendProcess.hProcess);
            CloseHandle(frontendProcess.hThread);
        }
    }

    int Run() {
        if (!VerifyInstallation()) {
            ShowErrorDialog(L"Installation appears to be incomplete.\n\nPlease reinstall the application.");
            return 1;
        }

        if (!StartBackend()) {
            return 2;
        }

        // Small delay to ensure backend is fully initialized
        std::this_thread::sleep_for(std::chrono::seconds(1));

        if (!StartFrontend()) {
            return 3;
        }

        WaitForExit();
        return 0;
    }
};

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    RDOLauncher launcher;
    return launcher.Run();
}

// Console entry point for debugging
int main() {
    RDOLauncher launcher;
    return launcher.Run();
}
#define _WIN32_WINNT 0x0602
#include <windows.h>
#include <wtsapi32.h>
#include <userenv.h>
#include <shellapi.h>
#include <string>
#pragma comment(lib, "wtsapi32.lib")
#pragma comment(lib, "userenv.lib")

static SERVICE_STATUS_HANDLE g_status_handle = NULL;
static SERVICE_STATUS g_status = {};
static HANDLE g_stop_event = NULL;
static HANDLE g_child_process = NULL;
static std::wstring g_dir;

static void update_status(DWORD state) {
    g_status.dwCurrentState = state;
    g_status.dwCheckPoint++;
    SetServiceStatus(g_status_handle, &g_status);
}

static void start_child() {
    std::wstring exe_path = g_dir + L"JustGivenUp.exe";

    DWORD session_id = WTSGetActiveConsoleSessionId();
    if (session_id == 0xFFFFFFFF) return;

    HANDLE hToken = NULL;
    if (!WTSQueryUserToken(session_id, &hToken)) return;

    HANDLE hPrimaryToken = NULL;
    if (!DuplicateTokenEx(hToken, TOKEN_ASSIGN_PRIMARY | TOKEN_ALL_ACCESS,
                          NULL, SecurityImpersonation, TokenPrimary, &hPrimaryToken)) {
        CloseHandle(hToken);
        return;
    }
    CloseHandle(hToken);

    PROCESS_INFORMATION pi = {};
    STARTUPINFOW si = { sizeof(si) };
    si.lpDesktop = const_cast<wchar_t*>(L"winsta0\\default");

    void* env = NULL;
    CreateEnvironmentBlock(&env, hPrimaryToken, FALSE);

    wchar_t cmd[MAX_PATH];
    wcscpy_s(cmd, exe_path.c_str());

    if (CreateProcessAsUserW(hPrimaryToken, exe_path.c_str(), cmd,
                             NULL, NULL, FALSE,
                             CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
                             env, NULL, &si, &pi)) {
        if (g_child_process) CloseHandle(g_child_process);
        g_child_process = pi.hProcess;
        CloseHandle(pi.hThread);
    }

    if (env) DestroyEnvironmentBlock(env);
    CloseHandle(hPrimaryToken);
}

static DWORD WINAPI service_handler(DWORD ctrl, DWORD, void*, void*) {
    switch (ctrl) {
        case SERVICE_CONTROL_STOP:
        case SERVICE_CONTROL_SHUTDOWN:
            update_status(SERVICE_STOP_PENDING);
            if (g_child_process) {
                TerminateProcess(g_child_process, 1);
                CloseHandle(g_child_process);
                g_child_process = NULL;
            }
            SetEvent(g_stop_event);
            return NO_ERROR;
        case SERVICE_CONTROL_INTERROGATE:
            return NO_ERROR;
    }
    return NO_ERROR;
}

static void WINAPI service_main(DWORD, wchar_t**) {
    g_status_handle = RegisterServiceCtrlHandlerExW(L"JustGivenUpSvc", service_handler, NULL);
    if (!g_status_handle) return;

    g_status.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
    g_status.dwControlsAccepted = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN;
    g_status.dwWin32ExitCode = NO_ERROR;
    update_status(SERVICE_RUNNING);

    g_stop_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!g_stop_event) return;

    start_child();

    while (WaitForSingleObject(g_stop_event, 1000) == WAIT_TIMEOUT) {
        if (g_child_process) {
            DWORD ret = WaitForSingleObject(g_child_process, 0);
            if (ret == WAIT_OBJECT_0) {
                CloseHandle(g_child_process);
                g_child_process = NULL;
                start_child();
            }
        } else {
            start_child();
        }
    }

    update_status(SERVICE_STOPPED);
    CloseHandle(g_stop_event);
}

static void install_service() {
    std::wstring exe_path = g_dir + L"JustGivenUpSvc.exe";
    SC_HANDLE scm = OpenSCManagerW(NULL, NULL, SC_MANAGER_CREATE_SERVICE);
    if (!scm) {
        MessageBoxW(NULL, L"Failed to open Service Control Manager.\nRun as Administrator.",
                    L"Error", MB_OK | MB_ICONERROR);
        return;
    }

    SC_HANDLE svc = CreateServiceW(scm, L"JustGivenUpSvc",
        L"JustGivenUp! Guardian Service",
        SERVICE_ALL_ACCESS, SERVICE_WIN32_OWN_PROCESS,
        SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
        exe_path.c_str(), NULL, NULL, NULL, NULL, NULL);
    if (!svc) {
        MessageBoxW(NULL, L"Failed to create service.\nIt may already exist.",
                    L"Error", MB_OK | MB_ICONERROR);
        CloseServiceHandle(scm);
        return;
    }

    // Auto-restart on failure
    SC_ACTION actions[] = { { SC_ACTION_RESTART, 3000 }, { SC_ACTION_RESTART, 10000 } };
    SERVICE_FAILURE_ACTIONSW fa = {};
    fa.dwResetPeriod = 86400;
    fa.cActions = 2;
    fa.lpsaActions = actions;
    ChangeServiceConfig2W(svc, SERVICE_CONFIG_FAILURE_ACTIONS, &fa);
    SERVICE_FAILURE_ACTIONS_FLAG flag = { TRUE };
    ChangeServiceConfig2W(svc, SERVICE_CONFIG_FAILURE_ACTIONS_FLAG, &flag);

    CloseServiceHandle(svc);
    CloseServiceHandle(scm);

    // Start service via sc (requires elevation)
    ShellExecuteW(NULL, L"runas", L"sc.exe",
                  L"start JustGivenUpSvc", NULL, SW_HIDE);

    // Launch tray app
    ShellExecuteW(NULL, L"open", (g_dir + L"JustGivenUp.exe").c_str(),
                  NULL, NULL, SW_SHOW);

    MessageBoxW(NULL, L"Service installed and started.\n"
                L"JustGivenUp! will restart automatically if killed.",
                L"JustGivenUp! Service", MB_OK | MB_ICONINFORMATION);
}

static void remove_service() {
    SC_HANDLE scm = OpenSCManagerW(NULL, NULL, SC_MANAGER_CONNECT);
    if (!scm) return;

    SC_HANDLE svc = OpenServiceW(scm, L"JustGivenUpSvc",
        SERVICE_STOP | DELETE | SERVICE_QUERY_STATUS);
    if (svc) {
        SERVICE_STATUS ss;
        ControlService(svc, SERVICE_CONTROL_STOP, &ss);
        DeleteService(svc);
        CloseServiceHandle(svc);
        MessageBoxW(NULL, L"Service removed.", L"JustGivenUp!",
                    MB_OK | MB_ICONINFORMATION);
    }
    CloseServiceHandle(scm);
}

int main() {
    wchar_t module[MAX_PATH];
    GetModuleFileNameW(NULL, module, MAX_PATH);
    wchar_t* last = wcsrchr(module, L'\\');
    if (last) *(last + 1) = L'\0';
    g_dir = module;

    SERVICE_TABLE_ENTRYW dispatch[] = {
        { L"JustGivenUpSvc", service_main },
        { NULL, NULL }
    };

    if (!StartServiceCtrlDispatcherW(dispatch)) {
        if (GetLastError() == ERROR_FAILED_SERVICE_CONTROLLER_CONNECT) {
            int choice = MessageBoxW(NULL,
                L"JustGivenUp! Guardian Service\n\n"
                L"Yes = Install service + Start\n"
                L"No = Remove service\n"
                L"Cancel = Exit",
                L"JustGivenUp! Service Installer",
                MB_YESNOCANCEL | MB_ICONQUESTION | MB_SYSTEMMODAL);

            if (choice == IDYES) install_service();
            else if (choice == IDNO) remove_service();
        }
    }
    return 0;
}

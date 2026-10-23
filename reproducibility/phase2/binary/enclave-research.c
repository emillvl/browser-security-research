/* Minimal owned non-debug VBS enclave. No network, files, or external operations. */
#include <winenclave.h>
const IMAGE_ENCLAVE_CONFIG __enclave_config = {
    sizeof(IMAGE_ENCLAVE_CONFIG),    IMAGE_ENCLAVE_MINIMUM_CONFIG_SIZE, 0, 0, 0,        0,
    {0x43, 0x52, 0x45, 0x53},        {0x50, 0x32, 0x30, 0x34},          1, 1, 0x200000, 1,
    IMAGE_ENCLAVE_FLAG_PRIMARY_IMAGE};
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) { return TRUE; }
__declspec(dllexport) void *CALLBACK ResearchCalculation(void *context) {
  return (void *)((ULONG_PTR)context ^ 0x137B6A94u);
}

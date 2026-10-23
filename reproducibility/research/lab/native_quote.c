/* Native counterparts of the browser workload for Ghidra analysis.
 * No network, filesystem, OS calls, or external dependencies. */
__declspec(dllexport) unsigned int quote(unsigned int x) { return (7 * x + 13) % 1009; }
static volatile const unsigned int program[] = {1, 7, 2, 1, 13, 3, 1, 1009, 4, 0};
__declspec(dllexport) __declspec(noinline) unsigned int quote_vm(unsigned int x) {
  unsigned int s[8], p = 0, sp = 0, m;
  for (;;) {
    switch (program[p++]) {
    case 0:
      return s[--sp];
    case 1:
      s[sp++] = program[p++];
      break;
    case 2:
      s[sp - 1] *= x;
      break;
    case 3:
      s[sp - 2] += s[sp - 1];
      --sp;
      break;
    case 4:
      m = s[--sp];
      s[sp - 1] %= m;
      break;
    default:
      return 0;
    }
  }
}

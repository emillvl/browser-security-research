// Export decompiled code from the native experiment binary.
// @category Research
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import java.io.*;

public class ExportResearch extends GhidraScript {
  public void run() throws Exception {
    String[] args = getScriptArgs();
    PrintWriter out = new PrintWriter(new FileWriter(args[0]));
    out.println("Program " + currentProgram.getName());
    out.println("Language " + currentProgram.getLanguageID());
    out.println("Compiler " + currentProgram.getCompilerSpec().getCompilerSpecID());
    DecompInterface decompiler = new DecompInterface();
    decompiler.openProgram(currentProgram);
    FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
    while (functions.hasNext()) {
      Function f = functions.next();
      if (f.isExternal())
        continue;
      out.println("\nFUNCTION " + f.getName() + " AT " + f.getEntryPoint());
      DecompileResults r = decompiler.decompileFunction(f, 30, monitor);
      if (r.decompileCompleted())
        out.println(r.getDecompiledFunction().getC());
      else
        out.println("DECOMPILATION ERROR " + r.getErrorMessage());
    }
    out.println("\nDATA BLOCKS");
    for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
      out.println(b.getName() + " " + b.getStart() + " size " + b.getSize());
      if (b.getName().equals(".rdata") || b.getName().equals(".data")) {
        int n = (int)Math.min(b.getSize(), 256);
        byte[] bytes = new byte[n];
        currentProgram.getMemory().getBytes(b.getStart(), bytes);
        for (int i = 0; i < n; i++) {
          out.printf("%02x", bytes[i] & 255);
          if (i % 32 == 31)
            out.println();
        }
        out.println();
      }
    }
    out.close();
    decompiler.dispose();
  }
}

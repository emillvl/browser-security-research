// @category Research
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import java.io.*;
public class RecoverForest extends GhidraScript {
  public void run() throws Exception {
    String[] args = getScriptArgs();
    PrintWriter out = new PrintWriter(new FileWriter(args[0]));
    out.println("Program " + currentProgram.getName() + " language " +
                currentProgram.getLanguageID());
    DecompInterface d = new DecompInterface();
    d.openProgram(currentProgram);
    FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
    while (functions.hasNext()) {
      Function f = functions.next();
      if (f.isExternal())
        continue;
      out.println("FUNCTION " + f.getName() + " at " + f.getEntryPoint());
      DecompileResults r = d.decompileFunction(f, 30, monitor);
      out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : r.getErrorMessage());
    }
    for (MemoryBlock block : currentProgram.getMemory().getBlocks())
      if (block.getName().equals(".rdata")) {
        byte[] b = new byte[(int)block.getSize()];
        currentProgram.getMemory().getBytes(block.getStart(), b);
        out.println("RODATA " + block.getStart() + " " + b.length);
        try (FileOutputStream stream = new FileOutputStream(args[1])) {
          stream.write(b);
        }
      }
    d.dispose();
    out.close();
  }
}

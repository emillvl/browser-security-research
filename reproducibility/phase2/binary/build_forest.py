"""Compile the forest model as a native interpreter without external dependencies."""

from pathlib import Path
import json, subprocess, hashlib

ROOT = Path(__file__).resolve().parents[1]
model = json.loads((ROOT / 'evidence/ground-truth.json').read_text())['model']
nodes = []
roots = []


def flatten(node):
    index = len(nodes)
    nodes.append(None)
    if 'value' in node:
        nodes[index] = [-1, 0, -1, -1, node['value']]
    else:
        left = flatten(node['left'])
        right = flatten(node['right'])
        nodes[index] = [node['feature'], node['threshold'], left, right, 0]
    return index


for tree in model['trees']:
    roots.append(flatten(tree))
source = (
    'typedef struct {int feature,threshold,left,right,value;} Node;\nstatic volatile const Node nodes[]={\n'
    + ',\n'.join('{' + ','.join(map(str, n)) + '}' for n in nodes)
    + '};\nstatic volatile const int roots[]={'
    + ','.join(map(str, roots))
    + '};\n'
)
source += '''__declspec(dllexport) __declspec(noinline) int dispatch_score(const int *input){
 for(int j=0;j<6;j++)if(input[j]<0||input[j]>1000)return -1;
 int total=0;for(int t=0;t<8;t++){int at=roots[t];while(nodes[at].feature>=0){int feature=nodes[at].feature;at=input[feature]<=nodes[at].threshold?nodes[at].left:nodes[at].right;}total+=nodes[at].value;}return total/8;
}
'''
target = ROOT / 'binary/forest.c'
target.write_text(source)
compiler = Path(
    r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe'
)
command = [
    str(compiler),
    '/nologo',
    '/O2',
    '/GS-',
    '/LD',
    str(target),
    '/Fo' + str(ROOT / 'binary/forest.obj'),
    '/link',
    '/NOENTRY',
    '/NODEFAULTLIB',
    '/OUT:' + str(ROOT / 'binary/forest.dll'),
    '/IMPLIB:' + str(ROOT / 'binary/forest.lib'),
]
result = subprocess.run(command, capture_output=True, text=True)
receipt = {
    'command': command,
    'exitCode': result.returncode,
    'stdout': result.stdout,
    'stderr': result.stderr,
    'nodes': len(nodes),
}
if result.returncode == 0:
    receipt['binarySHA256'] = hashlib.sha256((ROOT / 'binary/forest.dll').read_bytes()).hexdigest()
(ROOT / 'binary/build-receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
result.check_returncode()

"""a039 Register Swap -- construct one reusable permutation program across inputs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CONSOLE,REGISTER,SHAPE,SWAP,ROTATE,PROGRAM,GOAL,BAD=8,10,6,14,11,12,5,13,15
LEVELS=[{"name":"Adjacent Swap","seq":(1,)},{"name":"Rotate Three","seq":(2,1)},{"name":"Record Program","seq":(3,1,2)},{"name":"Next Input","seq":(4,2,1,3)},{"name":"Reusable Sequence","seq":(2,3,1,4,2,1)},{"name":"Register Swap","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 registers,index,program,example,history,compiled=s;r=list(registers);p=list(program)
 if a==1:i=index%3;r[i],r[i+1]=r[i+1],r[i];p.append((1,i))
 elif a==2:i=index%2;r[i:i+3]=r[i+1:i+3]+r[i:i+1];p.append((2,i))
 elif a==3:history=history+((example,tuple(r),tuple(p)),);index=(index+1)%3
 elif a==4:example=(example+1)%3;r=[(v+example)%4 for v in (0,1,2,3)];index=0
 elif a==5:compiled=(tuple(r),index,tuple(p[-6:]),example,history[-4:])
 return tuple(r),index,tuple(p),example,history,compiled
for x in LEVELS:
 s=((0,1,2,3),0,(),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CONSOLE
  for i,v in enumerate(g.registers):x=7+i*14;f[10:30,x:x+11]=REGISTER;f[18-v*3:26,x+2:x+9]=SHAPE
  f[34:40,7+g.index*14:32+g.index*14]=SWAP
  for i,(op,j) in enumerate(g.program[-5:]):f[44:49,8+i*10:16+i*10]=ROTATE if op==2 else PROGRAM
  if g.compiled:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A039(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a039",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.registers=(0,1,2,3);self.index=0;self.program=();self.example=0;self.history=();self.compiled=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.registers,self.index,self.program,self.example,self.history,self.compiled=advance((self.registers,self.index,self.program,self.example,self.history,self.compiled),a)
  elif a==6:
   if (self.registers,self.index,self.program,self.example,self.history,self.compiled)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

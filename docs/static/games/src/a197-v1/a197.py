"""a197 Reconfigurable Cell -- program a homogeneous field for several inputs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,ROUTE,STORE,TRANSFORM,BLOCK,CURSOR,PASS,ERROR,PATTERN=6,1,12,14,10,8,13,4,9,5
BAD=15
LEVELS=[
 {"name":"Set Cell Mode","seq":(1,)},{"name":"Move Cell","seq":(2,)},
 {"name":"Change Input","seq":(3,1)},{"name":"Test Program","seq":(1,2,3,4,2)},
 {"name":"Reuse Field","seq":(1,3,2,1,4,3,2)},{"name":"Reconfigurable Cell","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 modes,cursor,pattern,passed,errors,history,snapshot=s;m=list(modes)
 if a==1:m[cursor]=(m[cursor]+1)%4;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%16;history=(history+(2,))[-8:]
 elif a==3:pattern=(pattern+1)%4;cursor=(cursor+5)%16;history=(history+(3,))[-8:]
 elif a==4:
  checks=[sum(m[i] in ((i+p)%4,(i+p+1)%4) for i in range(16))>=8 for p in range(4)];passed=sum(checks);errors=4-passed;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(m),cursor,pattern,passed,errors,history)
 return tuple(m),cursor,pattern,passed,errors,history,snapshot
INITIAL=tuple((i*3+i//4)%4 for i in range(16))
for q in LEVELS:
 s=(INITIAL,0,0,4,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FIELD;cols=(ROUTE,STORE,TRANSFORM,BLOCK)
  for i,v in enumerate(g.modes):
   x=9+(i%4)*12;y=8+(i//4)*11;f[y:y+9,x:x+9]=cols[v]
   if i==g.cursor:f[y:y+2,x:x+9]=CURSOR
  f[52:56,8:8+g.passed*10]=PASS;f[52:56,48:48+g.errors*3]=ERROR;f[56:59,8+g.pattern*10:16+g.pattern*10]=PATTERN
  if g.bad:f[1:4,18:46]=BAD
  return f
class A197(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a197",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.modes,self.cursor,self.pattern,self.passed,self.errors,self.history,self.snapshot=(INITIAL,0,0,4,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.modes,self.cursor,self.pattern,self.passed,self.errors,self.history,self.snapshot=advance((self.modes,self.cursor,self.pattern,self.passed,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.modes,self.cursor,self.pattern,self.passed,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

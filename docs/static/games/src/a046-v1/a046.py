"""a046 Interrupt Loom -- preempt two resumable weaving automata at safe states."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CLOTH,WARP,WEAVER_A,WEAVER_B,SHUTTLE,SAFE,THREAD,MARK,BAD=6,9,8,12,14,10,13,11,4,15
LEVELS=[
 {"name":"Run A","seq":(1,)},{"name":"Safe Preempt","seq":(1,2,1)},
 {"name":"Preserve State","seq":(1,1,2,1,3)},{"name":"Share Shuttle","seq":(1,2,4,1,2)},
 {"name":"Nested Pattern","seq":(1,3,2,1,4,2,1)},{"name":"Interrupt Loom","seq":(1,2,1,3,4,1,2,3,1)},
]
def advance(s,a):
 pos,pattern,active,shuttle,blocked,history,snapshot=s;p=list(pos);pt=list(pattern)
 if a==1:
  p[active]=(p[active]+1+pt[active])%10;pt[active]=(pt[active]+1)%3;history=(history+(active,))[-8:]
 elif a==2:
  if p[active]%2==0:active^=1
  else:blocked=(blocked+1)%5
  history=(history+(2,))[-8:]
 elif a==3:
  other=active^1;p[other]=(p[other]+2)%10;pt[other]=(pt[other]+2)%3;history=(history+(3,))[-8:]
 elif a==4:
  if p[0]%2==0 or p[1]%2==0:shuttle^=1
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),tuple(pt),active,shuttle,blocked,history)
 return tuple(p),tuple(pt),active,shuttle,blocked,history,snapshot
for x in LEVELS:
 s=((0,2),(0,1),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,5:59]=CLOTH
  for x in range(9,57,6):f[7:55,x:x+2]=WARP
  for i,col in enumerate((WEAVER_A,WEAVER_B)):
   y=14+i*25;x=8+g.pos[i]*5;f[y:y+11,x:x+7]=col
   if g.pos[i]%2==0:f[y-4:y-1,x:x+7]=SAFE
   for j in range(g.pattern[i]+1):f[y+12+j*3:y+14+j*3,8:56]=THREAD
  sx=10+g.shuttle*38;f[29:35,sx:sx+8]=SHUTTLE
  f[7:12,26:38]=WEAVER_A if g.active==0 else WEAVER_B
  for i,v in enumerate(g.history[-8:]):f[55:58,10+i*5:14+i*5]=MARK if v in (2,4) else THREAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A046(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a046",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos,self.pattern,self.active,self.shuttle,self.blocked,self.history,self.snapshot=((0,2),(0,1),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.pattern,self.active,self.shuttle,self.blocked,self.history,self.snapshot=advance((self.pos,self.pattern,self.active,self.shuttle,self.blocked,self.history,self.snapshot),a)
  elif a==6:
   if (self.pos,self.pattern,self.active,self.shuttle,self.blocked,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

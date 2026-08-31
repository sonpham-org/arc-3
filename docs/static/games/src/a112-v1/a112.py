"""a112 Layered Bin -- pack cargo while preserving the future retrieval order."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WAREHOUSE,SHELF,CARGO_A,CARGO_B,DEPTH,REQUEST,EXPOSED,BLOCKED,BAD=9,8,7,12,14,10,13,4,6,15
LEVELS=[
 {"name":"Change Depth","seq":(1,)},{"name":"Select Cargo","seq":(2,)},
 {"name":"Change Column","seq":(3,1)},{"name":"Read Retrieval","seq":(1,2,3,4,2)},
 {"name":"Keep Exposed","seq":(1,3,2,1,4,3,2)},{"name":"Layered Bin","seq":(1,2,3,1,4,2,3,1,4,3)},
]
ORDER=(2,0,4,1,3)
def advance(s,a):
 depths,columns,cursor,step,exposed,blocked,history,snapshot=s;d=list(depths);c=list(columns)
 if a==1:d[cursor]=(d[cursor]+1)%4;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:c[cursor]=(c[cursor]+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  step=(step+1)%5;exposed=0;blocked=0
  for rank,item in enumerate(ORDER):
   ahead=sum(1 for earlier in ORDER[:rank] if c[earlier]==c[item] and d[earlier]<d[item]);exposed+=int(ahead==0);blocked+=ahead
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(d),tuple(c),cursor,step,exposed,blocked,history)
 return tuple(d),tuple(c),cursor,step,exposed,blocked,history,snapshot
for x in LEVELS:
 s=((0,1,2,3,1),(0,1,2,0,2),0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WAREHOUSE
  for layer in range(4):f[12+layer*10:20+layer*10,9:55]=SHELF
  for i,(depth,col) in enumerate(zip(g.depths,g.columns)):
   x=11+col*15+depth*2;y=13+depth*10;f[y:y+7,x:x+10]=CARGO_A if i%2==0 else CARGO_B
   if i==g.cursor:f[y-3:y,x:x+10]=DEPTH
  for rank,item in enumerate(ORDER):f[7:10,8+rank*9:15+rank*9]=REQUEST if rank!=g.step else EXPOSED
  f[54:58,8:8+min(7,g.blocked)*6]=BLOCKED
  if g.bad:f[1:4,18:46]=BAD
  return f
class A112(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a112",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.depths,self.columns,self.cursor,self.request_step,self.exposed,self.blocked,self.history,self.snapshot=((0,1,2,3,1),(0,1,2,0,2),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.depths,self.columns,self.cursor,self.request_step,self.exposed,self.blocked,self.history,self.snapshot=advance((self.depths,self.columns,self.cursor,self.request_step,self.exposed,self.blocked,self.history,self.snapshot),a)
  elif a==6:
   if (self.depths,self.columns,self.cursor,self.request_step,self.exposed,self.blocked,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

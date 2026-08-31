"""a044 Deadlock Dock -- grant and release locks without closing a cycle."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HARBOR,PIER,BOAT_A,BOAT_B,BOAT_C,LOCK,REQUEST,FREE,BAD=4,8,9,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Release First","seq":(1,)},{"name":"Grant Safely","seq":(1,2)},
 {"name":"Change Request","seq":(3,1,2)},{"name":"Break The Cycle","seq":(4,3,2,1)},
 {"name":"Ordered Grants","seq":(1,3,2,4,2,1)},{"name":"Deadlock Dock","seq":(3,1,4,2,3,2,1,4,2)},
]
def advance(s,a):
 owners,requester,cursor,released,ledger,snapshot=s;ow=list(owners)
 if a==1:
  for i,v in enumerate(ow):
   if v==cursor:ow[i]=-1;released=(released+(i,))[-4:];break
  ledger=(ledger+(1,))[-8:]
 elif a==2:
  want=(requester+1)%3
  if ow[want]==-1:ow[want]=requester
  requester=(requester+1)%3;ledger=(ledger+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;requester=(requester+2)%3;ledger=(ledger+(3,))[-8:]
 elif a==4:
  free=[i for i,v in enumerate(ow) if v==-1]
  if free:ow[free[0]]=cursor
  cursor=(cursor+2)%3;ledger=(ledger+(4,))[-8:]
 elif a==5:snapshot=(tuple(ow),requester,cursor,released,ledger)
 return tuple(ow),requester,cursor,released,ledger,snapshot
for x in LEVELS:
 s=((0,1,2),0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR
  for i,col in enumerate((BOAT_A,BOAT_B,BOAT_C)):
   x=8+i*18;f[14:29,x:x+14]=PIER;f[18:26,x+2:x+12]=col
   f[35:44,x+3:x+11]=LOCK;owner=g.owners[i];f[37:42,x+5:x+9]=FREE if owner<0 else (BOAT_A,BOAT_B,BOAT_C)[owner]
  xr=11+g.requester*18;f[9:13,xr:xr+8]=REQUEST
  xc=11+g.cursor*18;f[47:52,xc:xc+8]=FREE
  for i,v in enumerate(g.ledger[-8:]):f[54:57,10+i*5:14+i*5]=REQUEST if v==2 else LOCK
  if g.bad:f[1:4,18:46]=BAD
  return f
class A044(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a044",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.owners,self.requester,self.cursor,self.released,self.ledger,self.snapshot=((0,1,2),0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.owners,self.requester,self.cursor,self.released,self.ledger,self.snapshot=advance((self.owners,self.requester,self.cursor,self.released,self.ledger,self.snapshot),a)
  elif a==6:
   if (self.owners,self.requester,self.cursor,self.released,self.ledger,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

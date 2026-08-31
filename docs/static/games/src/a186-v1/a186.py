"""a186 Redundant Relay -- recover a message through transformed multipath copies."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,RELAY_A,RELAY_B,RELAY_C,FAILED,CURSOR,RECOVERED,ERROR,LINK=7,2,12,14,10,9,13,4,6,8
BAD=15
MESSAGE=0b101101
LEVELS=[
 {"name":"Route Copy","seq":(1,)},{"name":"Choose Relay","seq":(2,)},
 {"name":"Fail Channel","seq":(3,1)},{"name":"Invert Transform","seq":(1,2,3,4,2)},
 {"name":"Two of Three","seq":(1,3,2,1,4,3,2)},{"name":"Redundant Relay","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 routes,cursor,failed,recovered,errors,history,snapshot=s;r=list(routes)
 if a==1:r[cursor]^=1<<(cursor+1);history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:failed=(failed+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  live=[r[i]^(0b001011*(i+1)) for i in range(3) if i!=failed]
  recovered=sum(1 for b in range(6) if sum((v>>b)&1 for v in live)>=len(live)/2)
  decoded=sum((int(sum((v>>b)&1 for v in live)>=len(live)/2)<<b) for b in range(6))
  errors=(decoded^MESSAGE).bit_count();history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(r),cursor,failed,recovered,errors,history)
 return tuple(r),cursor,failed,recovered,errors,history,snapshot
INITIAL=(MESSAGE^0b001011,MESSAGE^0b010110,MESSAGE^0b100001)
for q in LEVELS:
 s=(INITIAL,0,2,4,2,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=FIELD
  for lane,val in enumerate(g.routes):
   y=11+lane*15;f[y:y+10,8:15]=FAILED if lane==g.failed else (RELAY_A,RELAY_B,RELAY_C)[lane]
   f[y+3:y+7,15:51]=LINK
   for b in range(6):f[y+1:y+9,19+b*6:24+b*6]=(RELAY_A,RELAY_B,RELAY_C)[lane] if (val>>b)&1 else BG
   if lane==g.cursor:f[y:y+10,52:56]=CURSOR
  f[54:58,8:8+g.recovered*7]=RECOVERED;f[7:10,8:8+g.errors*7]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A186(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a186",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.routes,self.cursor,self.failed,self.recovered,self.errors,self.history,self.snapshot=(INITIAL,0,2,4,2,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.routes,self.cursor,self.failed,self.recovered,self.errors,self.history,self.snapshot=advance((self.routes,self.cursor,self.failed,self.recovered,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.routes,self.cursor,self.failed,self.recovered,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

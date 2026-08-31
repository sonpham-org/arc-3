"""a139 Inverse Pair -- discover inverse machines by testing compositions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BENCH,MACHINE_A,MACHINE_B,CARGO,PAIR,PROBE,RESTORE,MOVED,ERROR=5,8,12,14,10,9,13,4,11,6
BAD=15
INVERSES=(2,3,0,1)
LEVELS=[
 {"name":"Choose Partner","seq":(1,)},{"name":"Select Machine","seq":(2,)},
 {"name":"Probe Pair","seq":(3,1)},{"name":"Test Composition","seq":(1,2,3,4,2)},
 {"name":"Restore Appearance","seq":(1,3,2,1,4,3,2)},{"name":"Inverse Pair","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 partners,cursor,probe,restored,moved,errors,history,snapshot=s;p=list(partners)
 if a==1:p[cursor]=(p[cursor]+1)%4;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:restored=sum(int(p[i]==INVERSES[i]) for i in range(4));moved=sum(int((i+p[i]+probe)%4!=i) for i in range(4));errors=4-restored;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),cursor,probe,restored,moved,errors,history)
 return tuple(p),cursor,probe,restored,moved,errors,history,snapshot
for q in LEVELS:
 s=((0,1,2,3),0,0,2,2,2,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i,p in enumerate(g.partners):
   y=11+i*11;f[y:y+8,8:18]=MACHINE_A;f[11+p*11:19+p*11,46:56]=MACHINE_B;f[min(y+3,14+p*11):max(y+4,15+p*11),18:46]=PAIR;f[y+2:y+6,11:15]=CARGO
   if i==g.cursor:f[y-3:y,7:19]=PROBE
  f[54:58,8:8+g.restored*9]=RESTORE;f[54:58,46:46+g.moved*3]=MOVED;f[7:10,8:8+g.errors*9]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A139(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a139",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.partners,self.cursor,self.probe,self.restored,self.moved,self.errors,self.history,self.snapshot=((0,1,2,3),0,0,2,2,2,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.partners,self.cursor,self.probe,self.restored,self.moved,self.errors,self.history,self.snapshot=advance((self.partners,self.cursor,self.probe,self.restored,self.moved,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.partners,self.cursor,self.probe,self.restored,self.moved,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

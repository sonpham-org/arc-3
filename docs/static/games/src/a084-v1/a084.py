"""a084 Truss Triage -- remove bars while retaining multi-direction rigidity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TUNNEL,BAR,ESSENTIAL,CURSOR,LOAD,VEHICLE,CLEAR,RIGID,BAD=12,8,9,14,10,11,13,6,4,15
LEVELS=[
 {"name":"Select Bar","seq":(2,)},{"name":"Remove One","seq":(1,)},
 {"name":"Change Load","seq":(3,1,2)},{"name":"Open Clearance","seq":(1,2,1,4,3)},
 {"name":"Keep Redundancy","seq":(2,1,3,2,1,4,3)},{"name":"Truss Triage","seq":(1,2,1,3,4,2,1,3,4,1)},
]
def advance(s,a):
 members,cursor,load,rigidity,clearance,vehicle,history,snapshot=s;m=list(members)
 if a==1:m[cursor]^=1;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:load=(load+1)%3;history=(history+(3,))[-8:]
 elif a==4:vehicle=(vehicle+1+clearance)%6;history=(history+(4,))[-8:]
 if a in (1,2,3,4):rigidity=sum(m[i] for i in ((0,2,4,6) if load%2==0 else (1,3,5,7)));clearance=sum(1-m[i] for i in (2,3,4))
 elif a==5:snapshot=(tuple(m),cursor,load,rigidity,clearance,vehicle,history)
 return tuple(m),cursor,load,rigidity,clearance,vehicle,history,snapshot
for x in LEVELS:
 s=((1,1,1,1,1,1,1,1),0,0,4,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TUNNEL;pts=((8,43),(20,17),(32,43),(44,17),(56,43))
  edges=((0,1),(1,2),(2,3),(3,4),(0,2),(1,3),(2,4),(0,4))
  for i,(u,v) in enumerate(edges):
   if not g.members[i]:continue
   x1,y1=pts[u];x2,y2=pts[v]
   for j in range(17):x=x1+(x2-x1)*j//16;y=y1+(y2-y1)*j//16;f[y:y+3,x:x+3]=ESSENTIAL if i in (0,3,7) else BAR
  x,y=pts[edges[g.cursor][0]];f[y-6:y-2,x:x+8]=CURSOR
  f[47:55,7+g.vehicle*8:14+g.vehicle*8]=VEHICLE;f[8:12,8:8+g.rigidity*8]=RIGID;f[12:16,45:57]=LOAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A084(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a084",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.members,self.cursor,self.load,self.rigidity,self.clearance,self.vehicle,self.history,self.snapshot=((1,1,1,1,1,1,1,1),0,0,4,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.members,self.cursor,self.load,self.rigidity,self.clearance,self.vehicle,self.history,self.snapshot=advance((self.members,self.cursor,self.load,self.rigidity,self.clearance,self.vehicle,self.history,self.snapshot),a)
  elif a==6:
   if (self.members,self.cursor,self.load,self.rigidity,self.clearance,self.vehicle,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

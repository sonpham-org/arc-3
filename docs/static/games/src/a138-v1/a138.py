"""a138 Commutator Lock -- exploit the residual of noncommuting transformations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LOCK,TILE,MARKER,OP_A,OP_B,INVERSE,TRACE,DISPLACE,DISTURB=4,8,7,12,10,14,13,9,4,6
BAD=15
LEVELS=[
 {"name":"Apply A","seq":(1,)},{"name":"Apply B","seq":(2,)},
 {"name":"Invert Operations","seq":(3,1)},{"name":"Form Commutator","seq":(1,2,3,4,2)},
 {"name":"Move Hidden Marker","seq":(1,3,2,1,4,3,2)},{"name":"Commutator Lock","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 marker,inverse,sequence,displacement,disturbance,history,snapshot=s;seq=sequence
 if a==1:marker=(marker+(-1 if inverse else 2))%9;seq=(seq+(1,))[-8:];history=(history+(1,))[-8:]
 elif a==2:marker=((marker^1) if marker<8 else marker);seq=(seq+(2,))[-8:];history=(history+(2,))[-8:]
 elif a==3:inverse=1-inverse;seq=(seq+(3,))[-8:];history=(history+(3,))[-8:]
 elif a==4:displacement=min((marker-4)%9,(4-marker)%9);disturbance=max(0,len(set(seq))-2)+int(seq[-4:] not in ((1,2,3,2),(2,1,3,1)));history=(history+(4,))[-8:]
 elif a==5:snapshot=(marker,inverse,seq,displacement,disturbance,history)
 return marker,inverse,seq,displacement,disturbance,history,snapshot
for q in LEVELS:
 s=(4,0,(),0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOCK
  for i in range(9):x=11+(i%3)*16;y=12+(i//3)*15;f[y:y+11,x:x+11]=MARKER if i==g.marker else TILE
  for i,v in enumerate(g.sequence):f[7:10,8+i*6:13+i*6]=OP_A if v==1 else OP_B if v==2 else INVERSE
  f[50:53,8:20]=OP_A;f[50:53,22:34]=OP_B;f[50:53,36:48]=INVERSE
  f[54:58,8:8+g.displacement*9]=DISPLACE;f[54:58,43:43+g.disturbance*6]=DISTURB
  if g.bad:f[1:4,18:46]=BAD
  return f
class A138(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a138",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.marker,self.inverse,self.sequence,self.displacement,self.disturbance,self.history,self.snapshot=(4,0,(),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.marker,self.inverse,self.sequence,self.displacement,self.disturbance,self.history,self.snapshot=advance((self.marker,self.inverse,self.sequence,self.displacement,self.disturbance,self.history,self.snapshot),a)
  elif a==6:
   if (self.marker,self.inverse,self.sequence,self.displacement,self.disturbance,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

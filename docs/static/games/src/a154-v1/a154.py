"""a154 Rule Boundary -- infer an oblique decision boundary with informative queries."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,PLOT,NEGATIVE,POSITIVE,QUERY,BOUNDARY,CURSOR,BUDGET,CORRECT,ERROR=5,8,12,14,10,9,13,11,4,6
BAD=15
POINTS=((1,1),(2,4),(4,1),(5,5),(3,3),(1,5),(5,2),(2,2))
LEVELS=[
 {"name":"Move Query Across","seq":(1,)},{"name":"Move Query Up","seq":(2,)},
 {"name":"Request Label","seq":(3,1)},{"name":"Fit Oblique Rule","seq":(1,2,3,4,2)},
 {"name":"Choose Informative Query","seq":(1,3,2,1,4,3,2)},{"name":"Rule Boundary","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 qx,qy,budget,slope,correct,errors,history,snapshot=s
 if a==1:qx=(qx+1)%6;history=(history+(1,))[-8:]
 elif a==2:qy=(qy+1)%6;history=(history+(2,))[-8:]
 elif a==3:budget=(budget+1)%5;slope=(slope+int(qx+qy>=5))%4;history=(history+(3,))[-8:]
 elif a==4:labels=[int(y*2>x+3+slope) for x,y in POINTS];correct=sum(int(v==int(y*2>x+3)) for v,(x,y) in zip(labels,POINTS));errors=8-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(qx,qy,budget,slope,correct,errors,history)
 return qx,qy,budget,slope,correct,errors,history,snapshot
for q in LEVELS:
 s=(0,0,0,0,8,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=PLOT
  for x,y in POINTS:
   px=9+x*8;py=53-y*8;f[py:py+6,px:px+6]=POSITIVE if y*2>x+3 else NEGATIVE
  for x in range(6):y=max(0,min(5,(x+3+g.slope)//2));px=9+x*8;py=53-y*8;f[py-2:py,px:px+7]=BOUNDARY
  px=9+g.qx*8;py=53-g.qy*8;f[py:py+7,px:px+7]=QUERY;f[7:10,8:8+g.budget*8]=BUDGET;f[54:58,8:8+g.correct*5]=CORRECT;f[54:58,50:50+g.errors*2]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A154(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a154",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.qx,self.qy,self.budget,self.slope,self.correct,self.errors,self.history,self.snapshot=(0,0,0,0,8,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.qx,self.qy,self.budget,self.slope,self.correct,self.errors,self.history,self.snapshot=advance((self.qx,self.qy,self.budget,self.slope,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.qx,self.qy,self.budget,self.slope,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

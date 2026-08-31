"""a156 Prototype Drift -- track a category center that moves after every success."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GALLERY,PROTOTYPE,CANDIDATE,STALE,ACCEPT,CURSOR,DRIFT,CURRENT,ERROR=7,8,12,14,9,4,13,10,11,6
BAD=15
CANDIDATES=((1,1),(2,1),(2,2),(3,2),(4,3),(4,4))
LEVELS=[
 {"name":"Select Candidate","seq":(1,)},{"name":"Accept Example","seq":(2,)},
 {"name":"Inspect History","seq":(3,1)},{"name":"Update Prototype","seq":(1,2,3,4,2)},
 {"name":"Ignore Stale Evidence","seq":(1,3,2,1,4,3,2)},{"name":"Prototype Drift","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 cursor,px,py,accepted,history_points,error,history,snapshot=s;hp=history_points
 if a==1:cursor=(cursor+1)%len(CANDIDATES);history=(history+(1,))[-8:]
 elif a==2:
  x,y=CANDIDATES[cursor];px=(px+x+1)//2;py=(py+y+1)//2;accepted=(accepted+1)%7;hp=(hp+((x,y),))[-5:];history=(history+(2,))[-8:]
 elif a==3:hp=hp[-3:];history=(history+(3,))[-8:]
 elif a==4:x,y=CANDIDATES[cursor];error=abs(x-px)+abs(y-py);history=(history+(4,))[-8:]
 elif a==5:snapshot=(cursor,px,py,accepted,hp,error,history)
 return cursor,px,py,accepted,hp,error,history,snapshot
for q in LEVELS:
 s=(0,1,1,0,(),0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i,(x,y) in enumerate(CANDIDATES):
   px=10+x*8;py=51-y*8;f[py:py+7,px:px+7]=CANDIDATE
   if i==g.cursor:f[py-3:py,px:px+7]=CURSOR
  for x,y in g.history_points:px=10+x*8;py=51-y*8;f[py+2:py+5,px+2:px+5]=STALE
  px=10+g.px*8;py=51-g.py*8;f[py:py+8,px:px+8]=PROTOTYPE;f[54:58,8:8+g.accepted*6]=ACCEPT;f[7:10,8:8+g.error*6]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A156(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a156",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cursor,self.px,self.py,self.accepted,self.history_points,self.error,self.history,self.snapshot=(0,1,1,0,(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cursor,self.px,self.py,self.accepted,self.history_points,self.error,self.history,self.snapshot=advance((self.cursor,self.px,self.py,self.accepted,self.history_points,self.error,self.history,self.snapshot),a)
  elif a==6:
   if (self.cursor,self.px,self.py,self.accepted,self.history_points,self.error,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

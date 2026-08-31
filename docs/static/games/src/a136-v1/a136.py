"""a136 Normal Form -- orient reversible rewrites toward one terminating representative."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,DESK,DIAGRAM,RULE_A,RULE_B,CURSOR,NORMAL,CYCLE,ORIENTATION,BAD=2,8,7,12,14,13,4,6,10,15
LEVELS=[
 {"name":"Apply Rewrite","seq":(1,)},{"name":"Select Diagram","seq":(2,)},
 {"name":"Set Orientation","seq":(3,1)},{"name":"Detect Cycle","seq":(1,2,3,4,2)},
 {"name":"Reduce Diagram","seq":(1,3,2,1,4,3,2)},{"name":"Normal Form","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 diagrams,cursor,orientation,normal,cycles,history,snapshot=s;d=list(diagrams)
 if a==1:d[cursor]=(d[cursor]+(1 if orientation==0 else 5))%6;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:orientation=1-orientation;history=(history+(3,))[-8:]
 elif a==4:normal=sum(int(x%3==0) for x in d);cycles=sum(int(x>=3) for x in d);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(d),cursor,orientation,normal,cycles,history)
 return tuple(d),cursor,orientation,normal,cycles,history,snapshot
for q in LEVELS:
 s=((0,1,2,3,4,5),0,0,2,3,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DESK
  for i,v in enumerate(g.diagrams):
   x=9+(i%3)*17;y=12+(i//3)*22;f[y:y+16,x:x+14]=DIAGRAM;f[y+3:y+7,x+3:x+11]=RULE_A if v%2==0 else RULE_B;f[y+9:y+12,x+3:x+3+(v%3+1)*3]=NORMAL
   if i==g.cursor:f[y-3:y,x:x+14]=CURSOR
  f[54:58,8:8+g.normal*7]=NORMAL;f[7:10,8:8+g.cycles*7]=CYCLE;f[54:58,50:57]=ORIENTATION
  if g.bad:f[1:4,18:46]=BAD
  return f
class A136(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a136",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.diagrams,self.cursor,self.orientation,self.normal,self.cycles,self.history,self.snapshot=((0,1,2,3,4,5),0,0,2,3,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.diagrams,self.cursor,self.orientation,self.normal,self.cycles,self.history,self.snapshot=advance((self.diagrams,self.cursor,self.orientation,self.normal,self.cycles,self.history,self.snapshot),a)
  elif a==6:
   if (self.diagrams,self.cursor,self.orientation,self.normal,self.cycles,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

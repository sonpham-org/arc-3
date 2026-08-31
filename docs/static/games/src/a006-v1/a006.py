"""a006 One-Sided Hinge -- test a branching sculpture from both approach directions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SCULPTURE,BRANCH,HINGE,MARBLE,TRAIL,DIRECTION,GOAL,BAD=5,10,8,14,11,6,12,13,15
LEVELS=[{"name":"Forward Marble","seq":(1,3)},{"name":"Reverse Marble","seq":(2,3)},{"name":"Directional Contrast","seq":(1,2,3)},{"name":"Leaf Rotation","seq":(4,2,1,3)},{"name":"Two-Sided Test","seq":(2,3,1,4,2,1,3)},{"name":"One-Sided Hinge","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 leaf,direction,fault,trails,marks,replaced=s
 if a==1:leaf=(leaf+1)%6;direction=1
 elif a==2:leaf=(leaf+2)%6;direction=-1
 elif a==3:path=tuple((leaf+i*direction)%6 for i in range(4));caught=int(fault in path and direction<0);trails=trails+((leaf,direction,path,caught),)
 elif a==4:marks=marks+((leaf,direction,trails[-2:]),);leaf=(leaf+3)%6;direction*=-1
 elif a==5:replaced=(fault,leaf,direction,trails[-4:],marks[-3:])
 return leaf,direction,fault,trails,marks,replaced
for x in LEVELS:
 s=(0,1,4,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SCULPTURE
  for i in range(6):x=8+(i%3)*18;y=8+(i//3)*14;f[y:y+10,x:x+13]=BRANCH;f[y+3:y+8,x+5:x+8]=HINGE;f[y+1:y+4,x+2:x+5]=MARBLE if i==g.leaf else DIRECTION
  for i,(_,d,_,caught) in enumerate(g.trails[-4:]):x=8+i*12;f[39:45,x:x+9]=TRAIL;f[46:49,x:x+5]=DIRECTION if d>0 else HINGE;f[50:53,x:x+3]=MARBLE if caught else BRANCH
  if g.replaced:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A006(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a006",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.leaf=0;self.direction=1;self.fault=4;self.trails=self.marks=();self.replaced=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.leaf,self.direction,self.fault,self.trails,self.marks,self.replaced=advance((self.leaf,self.direction,self.fault,self.trails,self.marks,self.replaced),a)
  elif a==6:
   if (self.leaf,self.direction,self.fault,self.trails,self.marks,self.replaced)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

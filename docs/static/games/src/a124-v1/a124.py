"""a124 Exists Exactly One -- configure nested existential and uniqueness constraints."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SCENE,GREEN,RED,BLUE,LINK,SELECT,EXACT,EXCESS,NONE=5,8,10,12,14,9,13,4,6,11
BAD=15
LEVELS=[
 {"name":"Toggle Link","seq":(1,)},{"name":"Select Lever","seq":(2,)},
 {"name":"Move Blue","seq":(3,1)},{"name":"Exactly One Red","seq":(1,2,3,4,2)},
 {"name":"Exists Blue None","seq":(1,3,2,1,4,3,2)},{"name":"Exists Exactly One","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 links,cursor,blue_pos,exact,blue_none,violations,history,snapshot=s
 if a==1:links^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%9;history=(history+(2,))[-8:]
 elif a==3:blue_pos=(blue_pos+1)%6;history=(history+(3,))[-8:]
 elif a==4:
  degrees=[sum((links>>(g*3+r))&1 for r in range(3)) for g in range(3)];exact=sum(int(d==1) for d in degrees);blue_none=int(all(((links>>(blue_pos%3*3+r))&1)==0 for r in range(3)));violations=sum(int(d!=1) for d in degrees)+int(not blue_none);history=(history+(4,))[-8:]
 elif a==5:snapshot=(links,cursor,blue_pos,exact,blue_none,violations,history)
 return links,cursor,blue_pos,exact,blue_none,violations,history,snapshot
for q in LEVELS:
 s=(0b001010100,0,0,3,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SCENE
  for i in range(3):
   gy=14+i*15;f[gy:gy+8,9:17]=GREEN;f[gy:gy+8,47:55]=RED
   for r in range(3):
    if (g.links>>(i*3+r))&1:f[min(gy+3,14+r*15+3):max(gy+4,14+r*15+4),17:47]=LINK
  by=12+(g.blue_pos%3)*15;f[by:by+8,27:35]=BLUE
  cx=8+(g.cursor%3)*17;cy=10+(g.cursor//3)*15;f[cy:cy+3,cx:cx+12]=SELECT
  f[54:58,8:8+g.exact*12]=EXACT;f[7:10,8:8+g.violations*9]=EXCESS if g.violations else NONE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A124(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a124",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.links,self.cursor,self.blue_pos,self.exact,self.blue_none,self.violations,self.history,self.snapshot=(0b001010100,0,0,3,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.links,self.cursor,self.blue_pos,self.exact,self.blue_none,self.violations,self.history,self.snapshot=advance((self.links,self.cursor,self.blue_pos,self.exact,self.blue_none,self.violations,self.history,self.snapshot),a)
  elif a==6:
   if (self.links,self.cursor,self.blue_pos,self.exact,self.blue_none,self.violations,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
